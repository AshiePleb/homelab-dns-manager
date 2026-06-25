"""Aggregate per-service health: DNS, HTTPS, backend port, DDNS sync."""

from __future__ import annotations

import asyncio
import socket

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DNSRecord, ProxyHost
from app.services.caddy_service import get_cert_expiry, get_ssl_status, probe_https
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


async def get_services_health(db: AsyncSession) -> list[dict]:
    result = await db.execute(select(ProxyHost).order_by(ProxyHost.hostname))
    hosts = result.scalars().all()
    rows: list[dict] = []

    for host in hosts:
        dns = await _resolve_dns(host.hostname)
        port = await check_port(host.forward_host, host.forward_port)
        https_ok, https_msg = await probe_https(host.hostname) if host.enabled else (False, "Proxy disabled")
        ssl = await get_ssl_status(host.hostname, has_proxy=True, ssl_mode=host.ssl_mode)
        expiry = get_cert_expiry(host.hostname)
        ssl_issuer = expiry["issuer"] if expiry else get_cert_issuer(host.hostname)

        r = await db.execute(
            select(DNSRecord)
            .where(DNSRecord.hostname == host.hostname, DNSRecord.managed == True)
            .limit(1)
        )
        dns_record = r.scalar_one_or_none()
        ssl_days = expiry["days_remaining"] if expiry else None

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
                "https_ok": https_ok,
                "https_message": https_msg,
                "port_ok": port["reachable"],
                "port_message": port["message"],
                "ssl_status": ssl["ssl_status"],
                "ssl_message": ssl["ssl_message"],
                "ssl_issuer": ssl_issuer,
                "ssl_days_remaining": ssl_days,
                "ssl_expires_at": expiry["expires_at"] if expiry else None,
                "ddns_managed": bool(dns_record),
                "ddns_last_sync": dns_record.last_updated_at if dns_record else None,
                "overall": _overall_status(
                    host.enabled, dns["ok"], port["reachable"], https_ok, ssl_days
                ),
            }
        )

    return rows
