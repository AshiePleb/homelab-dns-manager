"""Aggregate per-service health: DNS, HTTPS, backend port, DDNS sync."""

from __future__ import annotations

import asyncio
import socket

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DNSRecord, ProxyHost
from app.services.caddy_service import get_cert_expiry, get_ssl_status, probe_https, get_cert_issuer
from app.services.port_check import check_port

EXPIRY_WARN_DAYS = 14


async def _resolve_dns(hostname: str) -> dict:
    try:
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None, socket.getaddrinfo, hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM
        )
        addresses = sorted({item[4][0] for item in results})
        return {"ok": bool(addresses), "addresses": addresses, "message": ", ".join(addresses) or "No records"}
    except Exception as e:
        return {"ok": False, "addresses": [], "message": str(e) or "DNS lookup failed"}


def _overall_status(
    enabled: bool,
    dns_ok: bool,
    port_ok: bool,
    https_ok: bool,
    ssl_days: int | None,
) -> str:
    if not enabled:
        return "inactive"
    if not dns_ok or not port_ok:
        return "down"
    if not https_ok:
        return "degraded"
    if ssl_days is not None and ssl_days <= EXPIRY_WARN_DAYS:
        return "degraded"
    return "healthy"


async def _probe_host(host: ProxyHost) -> dict:
    """Network probes only — safe to run concurrently (no shared DB session)."""
    dns_task = _resolve_dns(host.hostname)
    port_task = check_port(host.forward_host, host.forward_port)
    if host.enabled:
        https_task = probe_https(host.hostname)
    else:
        https_task = asyncio.sleep(0, result=(False, "Proxy disabled"))

    dns, port, https_probe = await asyncio.gather(dns_task, port_task, https_task)
    https_ok, https_msg = https_probe
    ssl = await get_ssl_status(
        host.hostname,
        has_proxy=True,
        ssl_mode=host.ssl_mode,
        https_probe=https_probe,
    )
    expiry = get_cert_expiry(host.hostname)
    ssl_issuer = expiry["issuer"] if expiry else get_cert_issuer(host.hostname)
    ssl_days = expiry["days_remaining"] if expiry else None

    return {
        "dns": dns,
        "port": port,
        "https_ok": https_ok,
        "https_msg": https_msg,
        "ssl": ssl,
        "ssl_issuer": ssl_issuer,
        "ssl_days": ssl_days,
        "ssl_expires_at": expiry["expires_at"] if expiry else None,
    }


async def get_services_health(db: AsyncSession) -> list[dict]:
    result = await db.execute(select(ProxyHost).order_by(ProxyHost.hostname))
    hosts = list(result.scalars().all())
    if not hosts:
        return []

    hostnames = [h.hostname for h in hosts]
    dns_result = await db.execute(
        select(DNSRecord).where(
            DNSRecord.hostname.in_(hostnames),
            DNSRecord.managed == True,
        )
    )
    managed_by_host: dict[str, DNSRecord] = {}
    for record in dns_result.scalars().all():
        managed_by_host.setdefault(record.hostname, record)

    # Probe hosts concurrently — sequential checks made the dashboard hang for minutes.
    probes = await asyncio.gather(*(_probe_host(host) for host in hosts))

    rows: list[dict] = []
    for host, probe in zip(hosts, probes):
        dns = probe["dns"]
        port = probe["port"]
        dns_record = managed_by_host.get(host.hostname)
        rows.append(
            {
                "id": host.id,
                "hostname": host.hostname,
                "forward_host": host.forward_host,
                "forward_port": host.forward_port,
                "enabled": host.enabled,
                "dns_ok": dns["ok"],
                "dns_message": dns["message"],
                "dns_addresses": dns["addresses"],
                "https_ok": probe["https_ok"],
                "https_message": probe["https_msg"],
                "port_ok": port["reachable"],
                "port_message": port["message"],
                "ssl_status": probe["ssl"]["ssl_status"],
                "ssl_message": probe["ssl"]["ssl_message"],
                "ssl_issuer": probe["ssl_issuer"],
                "ssl_days_remaining": probe["ssl_days"],
                "ssl_expires_at": probe["ssl_expires_at"],
                "ddns_managed": bool(dns_record),
                "ddns_last_sync": dns_record.last_updated_at if dns_record else None,
                "overall": _overall_status(
                    host.enabled,
                    dns["ok"],
                    port["reachable"],
                    probe["https_ok"],
                    probe["ssl_days"],
                ),
            }
        )
    return rows
