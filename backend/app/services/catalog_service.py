"""Read-only catalog of linkable hostnames for external integrations."""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DNSRecord, ProxyHost
from app.services.caddy_service import get_cert_expiry, get_cert_issuer, get_ssl_status
from app.services.ddns_service import get_public_ip, get_stored_ip


def _map_ssl_status_for_catalog(
    *,
    internal_status: str,
    https_ok: bool,
    days_remaining: int | None,
) -> str:
    """Map internal SSL state to WebHost catalog values."""
    if days_remaining is not None and days_remaining < 0:
        return "expired"
    if days_remaining is not None and days_remaining <= 14:
        return "expiring"
    if internal_status == "active" and https_ok:
        return "working"
    if internal_status == "pending":
        return "unreachable"
    if internal_status == "warning" and https_ok:
        return "working"
    if internal_status == "warning":
        return "error"
    if not https_ok:
        return "unreachable"
    return "error"


async def _catalog_ssl_fields(hostname: str, *, ssl_mode: str | None) -> dict:
    ssl = await get_ssl_status(hostname, has_proxy=True, ssl_mode=ssl_mode)
    expiry = get_cert_expiry(hostname)
    issuer = get_cert_issuer(hostname)
    if not issuer and (ssl_mode or "letsencrypt") == "letsencrypt":
        issuer = "Let's Encrypt"

    days_remaining = expiry["days_remaining"] if expiry else None
    expires_at = expiry["expires_at"] if expiry else None
    https_ok = ssl["ssl_status"] == "active" or (
        ssl["ssl_status"] == "warning" and "HTTPS OK" in (ssl.get("ssl_message") or "")
    )

    status = _map_ssl_status_for_catalog(
        internal_status=ssl["ssl_status"],
        https_ok=https_ok,
        days_remaining=days_remaining,
    )

    fields: dict = {
        "ssl_status": status,
        "ssl_provider": issuer,
    }
    if expires_at:
        fields["ssl_expires_at"] = expires_at.isoformat()
    if days_remaining is not None:
        fields["ssl_days_left"] = days_remaining
    return fields


async def _catalog_ddns_fields(
    db: AsyncSession,
    dns: DNSRecord | None,
    *,
    stored_public_ip: str | None,
) -> dict:
    if not dns or dns.record_type != "A":
        return {}
    if not dns.managed:
        return {"public_ip": dns.content, "ddns_status": "static"}

    public_ip = dns.content
    fields: dict = {"public_ip": public_ip}
    if stored_public_ip:
        fields["ddns_status"] = "working" if public_ip == stored_public_ip else "stale"
    else:
        try:
            live_ip = await get_public_ip()
            fields["ddns_status"] = "working" if public_ip == live_ip else "stale"
        except Exception:
            fields["ddns_status"] = "unknown"
    return fields


async def list_linkable_catalog(db: AsyncSession) -> list[dict]:
    """
    All app linkable hostnames for WebHost auto-detect and domain linking.
    Built from Caddy proxy hosts; DNS record IDs and live SSL/DDNS status attached.
    """
    proxy_result = await db.execute(select(ProxyHost).order_by(ProxyHost.hostname))
    proxies = proxy_result.scalars().all()
    if not proxies:
        return []

    hostnames = [p.hostname for p in proxies]
    dns_result = await db.execute(
        select(DNSRecord).where(
            DNSRecord.hostname.in_(hostnames),
            DNSRecord.app_created.is_(True),
        )
    )
    dns_by_host: dict[str, DNSRecord] = {}
    for record in dns_result.scalars().all():
        existing = dns_by_host.get(record.hostname)
        if not existing or record.record_type == "A":
            dns_by_host[record.hostname] = record

    stored_public_ip = await get_stored_ip(db)

    ssl_fields_list = await asyncio.gather(
        *(_catalog_ssl_fields(p.hostname, ssl_mode=p.ssl_mode) for p in proxies)
    )

    catalog: list[dict] = []
    for proxy, ssl_fields in zip(proxies, ssl_fields_list):
        dns = dns_by_host.get(proxy.hostname)
        owned_via_api = proxy.api_key_id is not None or (dns is not None and dns.api_key_id is not None)
        entry: dict = {
            "hostname": proxy.hostname,
            "internal_target": f"{proxy.forward_host}:{proxy.forward_port}",
            "dns_record_id": dns.id if dns else None,
            "dns_service_id": proxy.id,
            "managed_by": "api" if owned_via_api else "panel",
        }
        entry.update(ssl_fields)
        entry.update(await _catalog_ddns_fields(db, dns, stored_public_ip=stored_public_ip))
        catalog.append(entry)

    return catalog
