"""Provision homelab services: subdomain + target → Cloudflare DNS + built-in Caddy proxy."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ProxyHost, LogLevel, DNSRecord
from app.services.bootstrap_service import ensure_managed_ddns_hostname
from app.services.ddns_service import get_public_ip
from app.services.settings_service import get_setting, log_activity
from app.services.port_check import check_port
from app.services.caddy_service import write_all_sites, reload_caddy


def normalize_subdomain(subdomain: str) -> str:
    return subdomain.strip().lower().lstrip("*.")


def build_fqdn(subdomain: str, base_domain: str) -> str:
    base = base_domain.strip().lower().rstrip(".")
    sub = normalize_subdomain(subdomain)
    if not sub or sub in ("@", "root"):
        return base
    if sub == base or sub.endswith(f".{base}"):
        return sub
    if "." in sub:
        return sub
    return f"{sub}.{base}"


def parse_host_port(target: str, default_port: int = 80) -> tuple[str, int]:
    target = target.strip()
    if not target:
        raise ValueError("Target host is required")
    if ":" in target:
        host, _, port_str = target.rpartition(":")
        if port_str.isdigit():
            return host.strip(), int(port_str)
    return target, default_port


async def get_default_zone(db: AsyncSession) -> str | None:
    return await get_setting(db, "general.default_zone")


async def set_default_zone(db: AsyncSession, zone: str) -> None:
    from app.services.settings_service import set_setting
    await set_setting(db, "general.default_zone", zone.strip().lower())


async def infer_default_zone_from_hostnames(hostnames: list[str]) -> str | None:
    if not hostnames:
        return None
    candidates: set[str] = set()
    for host in hostnames:
        parts = host.lower().split(".")
        for i in range(len(parts) - 1):
            candidates.add(".".join(parts[i:]))
    return min(candidates, key=len) if candidates else None


async def _sync_caddy(db: AsyncSession) -> None:
    result = await db.execute(select(ProxyHost).where(ProxyHost.enabled == True))
    hosts = result.scalars().all()
    write_all_sites(
        [
            {
                "hostname": h.hostname,
                "forward_host": h.forward_host,
                "forward_port": h.forward_port,
                "ssl_mode": h.ssl_mode,
                "enabled": h.enabled,
            }
            for h in hosts
        ]
    )
    reload_caddy()


async def provision_service(
    db: AsyncSession,
    *,
    subdomain: str,
    forward_host: str,
    forward_port: int,
    base_domain: str | None = None,
    ssl_mode: str = "letsencrypt",
    create_dns: bool = True,
    create_proxy: bool = True,
    skip_port_check: bool = False,
    user_id: int | None = None,
    api_key_id: int | None = None,
) -> dict:
    zone = base_domain or await get_default_zone(db)
    if not zone:
        raise ValueError("No default domain configured. Set it in Settings → General.")

    hostname = build_fqdn(subdomain, zone)
    proxied = False  # grey cloud — Caddy handles HTTPS via Let's Encrypt
    public_ip: str | None = None
    dns_record_id: int | None = None
    proxy_host_id: int | None = None
    port_status = await check_port(forward_host, forward_port)

    if not skip_port_check and not port_status["reachable"]:
        raise ValueError(
            f"Port {forward_port} on {forward_host} is not reachable: {port_status['message']}. "
            "Check firewall/router port forwarding, or enable 'Skip port check'."
        )

    if create_dns:
        if api_key_id is not None:
            from app.services.api_key_service import ensure_dns_limit
            from app.models import ApiKey
            from sqlalchemy import select as sa_select

            key_row = await db.get(ApiKey, api_key_id)
            if key_row:
                existing_dns = await db.execute(
                    sa_select(DNSRecord).where(
                        DNSRecord.hostname == hostname, DNSRecord.api_key_id == api_key_id
                    )
                )
                if not existing_dns.scalar_one_or_none():
                    await ensure_dns_limit(db, key_row)
        public_ip = await get_public_ip()
        record = await ensure_managed_ddns_hostname(
            db, hostname, proxied=proxied, current_ip=public_ip, api_key_id=api_key_id
        )
        if not record:
            raise ValueError(f"Failed to create Cloudflare DNS record for {hostname}")
        record.app_created = True
        if api_key_id is not None:
            record.api_key_id = api_key_id
        dns_record_id = record.id

    if create_proxy:
        existing = await db.execute(select(ProxyHost).where(ProxyHost.hostname == hostname))
        proxy = existing.scalar_one_or_none()
        proxy_created = proxy is None
        if proxy and api_key_id is not None and proxy.api_key_id not in (None, api_key_id):
            raise ValueError(f"Hostname {hostname} is already used by another service")
        if not proxy and api_key_id is not None:
            from app.services.api_key_service import ensure_service_limit
            from app.models import ApiKey

            key_row = await db.get(ApiKey, api_key_id)
            if key_row:
                await ensure_service_limit(db, key_row)
        if proxy:
            proxy.forward_host = forward_host
            proxy.forward_port = forward_port
            proxy.ssl_mode = ssl_mode
            proxy.port_reachable = port_status["reachable"]
            proxy.last_port_check = datetime.now(timezone.utc)
            if api_key_id is not None:
                proxy.api_key_id = api_key_id
        else:
            proxy = ProxyHost(
                hostname=hostname,
                forward_host=forward_host,
                forward_port=forward_port,
                ssl_mode=ssl_mode,
                port_reachable=port_status["reachable"],
                last_port_check=datetime.now(timezone.utc),
                api_key_id=api_key_id,
            )
            db.add(proxy)
        await db.flush()
        proxy_host_id = proxy.id
        await _sync_caddy(db)
    else:
        proxy_created = False

    ssl_label = "Caddy HTTPS (Let's Encrypt)"
    mapping = f"{hostname} → {forward_host}:{forward_port} [{ssl_label}]"
    if public_ip:
        mapping += f" · DNS A → {public_ip}"

    await log_activity(
        db,
        "service",
        f"{'Provisioned' if proxy_created else 'Updated'} {hostname}",
        LogLevel.SUCCESS,
        details={
            "hostname": hostname,
            "ssl_mode": ssl_mode,
            "port": port_status,
            "api_key_id": api_key_id,
            "created": proxy_created,
        },
        user_id=user_id,
    )

    # Only notify on first create — upserts / double-submits must not spam Discord
    if proxy_created or (create_dns and not create_proxy):
        from app.services.notification_service import send_notifications
        await send_notifications(
            db,
            "service_created",
            {
                "hostname": hostname,
                "target": f"{forward_host}:{forward_port}",
                "ssl_mode": ssl_mode,
            },
        )

    return {
        "hostname": hostname,
        "base_domain": zone,
        "subdomain": subdomain,
        "forward_host": forward_host,
        "forward_port": forward_port,
        "public_ip": public_ip,
        "proxied": proxied,
        "ssl_mode": ssl_mode,
        "dns_record_id": dns_record_id,
        "proxy_host_id": proxy_host_id,
        "port_reachable": port_status["reachable"],
        "port_message": port_status["message"],
        "mapping": mapping,
        "created": proxy_created if create_proxy else True,
    }


async def update_service_target(
    db: AsyncSession,
    proxy_id: int,
    *,
    forward_host: str,
    forward_port: int,
    skip_port_check: bool = False,
    user_id: int | None = None,
    api_key_id: int | None = None,
) -> dict:
    """Update upstream host:port for an existing proxy and reload Caddy."""
    result = await db.execute(select(ProxyHost).where(ProxyHost.id == proxy_id))
    proxy = result.scalar_one_or_none()
    if not proxy:
        raise ValueError("Service not found")
    if api_key_id is not None and proxy.api_key_id != api_key_id:
        raise ValueError("Service not found")

    host = forward_host.strip()
    if not host:
        raise ValueError("Target host is required")
    if forward_port < 1 or forward_port > 65535:
        raise ValueError("Port must be between 1 and 65535")

    port_status = await check_port(host, forward_port)
    if not skip_port_check and not port_status["reachable"]:
        raise ValueError(
            f"Port {forward_port} on {host} is not reachable: {port_status['message']}. "
            "Check firewall/router port forwarding, or enable 'Skip port check'."
        )

    old_target = f"{proxy.forward_host}:{proxy.forward_port}"
    new_target = f"{host}:{forward_port}"
    if old_target == new_target:
        return {
            "id": proxy.id,
            "hostname": proxy.hostname,
            "forward_host": proxy.forward_host,
            "forward_port": proxy.forward_port,
            "port_reachable": proxy.port_reachable,
            "port_message": port_status["message"],
            "mapping": f"{proxy.hostname} → {new_target}",
            "changed": False,
            "caddy_reloaded": False,
        }

    proxy.forward_host = host
    proxy.forward_port = forward_port
    proxy.port_reachable = port_status["reachable"]
    proxy.last_port_check = datetime.now(timezone.utc)
    await db.flush()
    await _sync_caddy(db)

    await log_activity(
        db,
        "service",
        f"Updated {proxy.hostname}: {old_target} → {new_target}",
        LogLevel.SUCCESS,
        details={"hostname": proxy.hostname, "old_target": old_target, "new_target": new_target},
        user_id=user_id,
    )

    return {
        "id": proxy.id,
        "hostname": proxy.hostname,
        "forward_host": proxy.forward_host,
        "forward_port": proxy.forward_port,
        "port_reachable": port_status["reachable"],
        "port_message": port_status["message"],
        "mapping": f"{proxy.hostname} → {new_target}",
        "changed": True,
        "caddy_reloaded": True,
    }


async def delete_service(
    db: AsyncSession,
    proxy_id: int,
    user_id: int | None = None,
    api_key_id: int | None = None,
) -> None:
    result = await db.execute(select(ProxyHost).where(ProxyHost.id == proxy_id))
    host = result.scalar_one_or_none()
    if not host:
        raise ValueError("Service not found")
    if api_key_id is not None and host.api_key_id != api_key_id:
        raise ValueError("Service not found")
    hostname = host.hostname
    await db.delete(host)
    await db.flush()
    await _sync_caddy(db)
    await log_activity(db, "service", f"Removed proxy for {hostname}", LogLevel.WARNING, user_id=user_id)
    from app.services.notification_service import send_notifications
    await send_notifications(db, "service_deleted", {"hostname": hostname})


async def list_provisioned_services(db: AsyncSession) -> list[dict]:
    from app.models import DNSRecord

    result = await db.execute(select(ProxyHost).order_by(ProxyHost.id))
    hosts = result.scalars().all()
    services = []

    for h in hosts:
        r = await db.execute(
            select(DNSRecord).where(
                DNSRecord.hostname == h.hostname, DNSRecord.app_created == True
            ).limit(1)
        )
        dns = r.scalar_one_or_none()
        ssl_label = "Caddy HTTPS"
        services.append({
            "id": h.id,
            "hostname": h.hostname,
            "forward_host": h.forward_host,
            "forward_port": h.forward_port,
            "ssl_mode": h.ssl_mode,
            "ssl_label": ssl_label,
            "enabled": h.enabled,
            "port_reachable": h.port_reachable,
            "mapping": f"{h.hostname} → {h.forward_host}:{h.forward_port}",
            "dns_managed": bool(dns and dns.managed),
            "dns_proxied": dns.proxied if dns else None,
            "public_ip": dns.content if dns else None,
        })

    return services
