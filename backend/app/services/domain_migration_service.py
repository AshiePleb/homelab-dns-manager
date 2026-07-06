"""Migrate app-managed services to a new base domain without changing record/proxy IDs."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import DNSRecord, DNSRecordHistory, Domain, HealthCheckHistory, LogLevel, ProxyHost
from app.services.cloudflare_service import get_cloudflare_service, sync_zones
from app.services.ddns_service import get_public_ip
from app.services.service_provision import _sync_caddy, build_fqdn
from app.services.settings_service import log_activity


def extract_subdomain(hostname: str, zone_name: str) -> str:
    """Subdomain label relative to zone (e.g. home.example.com + example.com → home)."""
    host = hostname.lower().strip().rstrip(".")
    zone = zone_name.lower().strip().rstrip(".")
    if host == zone:
        return "@"
    suffix = f".{zone}"
    if host.endswith(suffix):
        return host[: -len(suffix)]
    raise ValueError(f"{hostname} is not under zone {zone_name}")


def compute_new_hostname(record: DNSRecord, target_domain: str) -> str:
    if not record.domain:
        raise ValueError(f"Record {record.id} has no linked domain")
    subdomain = extract_subdomain(record.hostname, record.domain.name)
    return build_fqdn(subdomain, target_domain)


async def _hostname_in_use(
    db: AsyncSession,
    hostname: str,
    *,
    exclude_record_id: int | None = None,
    exclude_proxy_id: int | None = None,
) -> bool:
    q = select(DNSRecord.id).where(DNSRecord.hostname == hostname)
    if exclude_record_id is not None:
        q = q.where(DNSRecord.id != exclude_record_id)
    if await db.scalar(q.limit(1)):
        return True
    pq = select(ProxyHost.id).where(ProxyHost.hostname == hostname)
    if exclude_proxy_id is not None:
        pq = pq.where(ProxyHost.id != exclude_proxy_id)
    return bool(await db.scalar(pq.limit(1)))


async def migrate_records_to_domain(
    db: AsyncSession,
    *,
    record_ids: list[int],
    target_domain: str,
    dry_run: bool = False,
    user_id: int | None = None,
) -> dict:
    target_domain = target_domain.strip().lower().rstrip(".")
    if not target_domain:
        raise ValueError("Target domain is required")

    cf = await get_cloudflare_service(db)
    if not cf and not dry_run:
        raise ValueError("Cloudflare not configured")

    zones = await sync_zones(db)
    target_zone = next((z for z in zones if z.name.lower() == target_domain), None)
    if not target_zone:
        domain_row = await db.execute(select(Domain).where(Domain.name == target_domain))
        target_zone = domain_row.scalar_one_or_none()
    if not target_zone:
        raise ValueError(f"Zone {target_domain} not found. Sync domains in Cloudflare first.")

    results: list[dict] = []
    errors: list[str] = []
    migrated = 0
    proxy_id_by_record: dict[int, int | None] = {}

    for record_id in record_ids:
        result = await db.execute(
            select(DNSRecord)
            .options(selectinload(DNSRecord.domain))
            .where(DNSRecord.id == record_id)
        )
        record = result.scalar_one_or_none()
        if not record:
            errors.append(f"Record {record_id} not found")
            continue
        if not record.app_created:
            errors.append(f"{record.hostname}: only app-managed records can be migrated")
            continue

        proxy_result = await db.execute(
            select(ProxyHost).where(ProxyHost.hostname == record.hostname)
        )
        proxy = proxy_result.scalar_one_or_none()
        proxy_id_by_record[record_id] = proxy.id if proxy else None

        try:
            new_hostname = compute_new_hostname(record, target_domain)
        except ValueError as e:
            errors.append(str(e))
            continue

        old_hostname = record.hostname
        if new_hostname == old_hostname:
            errors.append(f"{old_hostname}: already on {target_domain}")
            continue

        if await _hostname_in_use(
            db,
            new_hostname,
            exclude_record_id=record.id,
            exclude_proxy_id=proxy.id if proxy else None,
        ):
            errors.append(f"{old_hostname}: {new_hostname} already exists")
            continue

        item = {
            "record_id": record.id,
            "proxy_id": proxy.id if proxy else None,
            "old_hostname": old_hostname,
            "new_hostname": new_hostname,
            "migrated": False,
        }
        results.append(item)

        if dry_run:
            item["migrated"] = True
            migrated += 1
            continue

        old_zone = record.domain
        old_cf_id = record.cloudflare_record_id
        ip_content = record.content
        if record.managed and record.record_type == "A":
            try:
                ip_content = await get_public_ip()
            except Exception:
                ip_content = record.content

        try:
            cf_rec = await cf.create_record(
                target_zone.zone_id,
                {
                    "type": record.record_type,
                    "name": new_hostname,
                    "content": ip_content,
                    "ttl": record.ttl,
                    "proxied": record.proxied,
                },
            )
        except Exception as e:
            errors.append(f"{old_hostname}: failed to create DNS in {target_domain}: {e}")
            continue

        record.domain_id = target_zone.id
        record.hostname = new_hostname
        record.cloudflare_record_id = cf_rec["id"]
        if record.record_type == "A":
            record.content = ip_content
        record.last_updated_at = datetime.now(timezone.utc)

        db.add(
            DNSRecordHistory(
                record_id=record.id,
                old_content=old_hostname,
                new_content=new_hostname,
                change_reason="domain_migration",
            )
        )

        if proxy:
            proxy.hostname = new_hostname

        await db.execute(
            update(HealthCheckHistory)
            .where(HealthCheckHistory.hostname == old_hostname)
            .values(hostname=new_hostname)
        )

        if old_cf_id and old_zone:
            try:
                await cf.delete_record(old_zone.zone_id, old_cf_id)
            except Exception as e:
                errors.append(
                    f"{old_hostname}: migrated to {new_hostname} but old Cloudflare record may remain: {e}"
                )

        remove_stored_cert(old_hostname)
        item["migrated"] = True
        migrated += 1

    caddy_reloaded = False
    if not dry_run and migrated > 0:
        await _sync_caddy(db)
        caddy_reloaded = True
        await log_activity(
            db,
            "dns",
            f"Migrated {migrated} service(s) to {target_domain}",
            LogLevel.SUCCESS,
            details={"target_domain": target_domain, "results": results},
            user_id=user_id,
        )

    return {
        "dry_run": dry_run,
        "target_domain": target_domain,
        "migrated": migrated,
        "results": results,
        "errors": errors,
        "caddy_reloaded": caddy_reloaded,
    }
