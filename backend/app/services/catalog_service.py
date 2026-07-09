"""Read-only catalog of linkable hostnames for external integrations."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DNSRecord, ProxyHost


async def list_linkable_catalog(db: AsyncSession) -> list[dict]:
    """
    All app linkable hostnames for WebHost auto-detect and domain linking.
    Built from Caddy proxy hosts; DNS record IDs attached when present.
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

    catalog: list[dict] = []
    for proxy in proxies:
        dns = dns_by_host.get(proxy.hostname)
        owned_via_api = proxy.api_key_id is not None or (dns is not None and dns.api_key_id is not None)
        catalog.append(
            {
                "hostname": proxy.hostname,
                "internal_target": f"{proxy.forward_host}:{proxy.forward_port}",
                "dns_record_id": dns.id if dns else None,
                "dns_service_id": proxy.id,
                "managed_by": "api" if owned_via_api else "panel",
            }
        )

    return catalog
