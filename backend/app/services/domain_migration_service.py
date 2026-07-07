"""Migrate app-managed services to a new base domain without changing record/proxy IDs."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import DNSRecord, DNSRecordHistory, Domain, HealthCheckHistory, LogLevel, ProxyHost
from app.services.caddy_service import remove_stored_cert
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


def resolve_new_hostname(
    record: DNSRecord,
    target_domain: str,
    subdomain_override: str | None = None,
) -> str:
    if not record.domain:
        raise ValueError(f"Record {record.id} has no linked domain")
    if subdomain_override is not None:
        sub = subdomain_override.strip().lower()
        if not sub:
            raise ValueError(f"Record {record.id}: subdomain cannot be empty")
        return build_fqdn(sub, target_domain)
    subdomain = extract_subdomain(record.hostname, record.domain.name)
    return build_fqdn(subdomain, target_domain)


def _cf_record_name_matches(record_name: str, fqdn: str, zone_name: str) -> bool:
    name = record_name.lower().strip().rstrip(".")
    host = fqdn.lower().strip().rstrip(".")
    zone = zone_name.lower().strip().rstrip(".")
    return name == host or (name == "@" and host == zone)


async def _get_migration_hostname_conflict(
    db: AsyncSession,
    hostname: str,
    *,
    exclude_record_id: int | None = None,
    exclude_proxy_id: int | None = None,
) -> str | None:
    """Only app-managed DNS rows and proxy hosts block migration (not CF sync-only rows)."""
    q = select(DNSRecord).where(DNSRecord.hostname == hostname, DNSRecord.app_created.is_(True))
    if exclude_record_id is not None:
        q = q.where(DNSRecord.id != exclude_record_id)
    conflict = (await db.execute(q.limit(1))).scalar_one_or_none()
    if conflict:
        return f"app-managed DNS record (id {conflict.id})"

    pq = select(ProxyHost).where(ProxyHost.hostname == hostname)
    if exclude_proxy_id is not None:
        pq = pq.where(ProxyHost.id != exclude_proxy_id)
    proxy = (await db.execute(pq.limit(1))).scalar_one_or_none()
    if proxy:
        return f"reverse proxy (id {proxy.id})"
    return None


async def _remove_synced_hostname_rows(
    db: AsyncSession,
    hostname: str,
    *,
    keep_record_id: int,
    record_type: str,
) -> None:
    result = await db.execute(
        select(DNSRecord).where(
            DNSRecord.hostname == hostname,
            DNSRecord.id != keep_record_id,
            DNSRecord.app_created.is_(False),
            DNSRecord.record_type == record_type.upper(),
        )
    )
    for row in result.scalars().all():
        await db.delete(row)


async def _create_or_update_cf_record(
    cf,
    zone_id: str,
    zone_name: str,
    *,
    record_type: str,
    hostname: str,
    content: str,
    ttl: int,
    proxied: bool,
) -> dict:
    record_type = record_type.upper()
    same_type: dict | None = None
    blocking: dict | None = None
    for rec in await cf.list_records(zone_id):
        if not _cf_record_name_matches(rec.get("name", ""), hostname, zone_name):
            continue
        rec_type = (rec.get("type") or "").upper()
        if rec_type == record_type:
            same_type = rec
            break
        if rec_type in {"A", "AAAA", "CNAME"}:
            blocking = rec

    payload = {
        "type": record_type,
        "name": hostname,
        "content": content,
        "ttl": ttl,
        "proxied": proxied,
    }
    if same_type:
        return await cf.update_record(zone_id, same_type["id"], payload)
    if blocking:
        raise ValueError(
            f"Cloudflare already has a {blocking['type']} record for {hostname}; "
            f"remove it or pick a different subdomain"
        )
    return await cf.create_record(zone_id, payload)


async def migrate_records_to_domain(
    db: AsyncSession,
    *,
    record_ids: list[int],
    target_domain: str,
    dry_run: bool = False,
    subdomain_overrides: dict[int, str] | None = None,
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

    overrides = subdomain_overrides or {}
    results: list[dict] = []
    errors: list[str] = []
    migrated = 0

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

        override = overrides.get(record_id)
        try:
            new_hostname = resolve_new_hostname(record, target_domain, override)
            subdomain_used = (
                override
                if override is not None
                else extract_subdomain(record.hostname, record.domain.name)
            )
        except ValueError as e:
            errors.append(str(e) if str(e).startswith(record.hostname) else f"{record.hostname}: {e}")
            continue

        old_hostname = record.hostname
        if new_hostname == old_hostname:
            errors.append(f"{old_hostname}: already on {target_domain} with this subdomain")
            continue

        conflict = await _get_migration_hostname_conflict(
            db,
            new_hostname,
            exclude_record_id=record.id,
            exclude_proxy_id=proxy.id if proxy else None,
        )
        if conflict:
            errors.append(f"{old_hostname}: {new_hostname} already in use ({conflict})")
            continue

        item = {
            "record_id": record.id,
            "proxy_id": proxy.id if proxy else None,
            "old_hostname": old_hostname,
            "new_hostname": new_hostname,
            "subdomain": subdomain_used,
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
            cf_rec = await _create_or_update_cf_record(
                cf,
                target_zone.zone_id,
                target_zone.name,
                record_type=record.record_type,
                hostname=new_hostname,
                content=ip_content,
                ttl=record.ttl,
                proxied=record.proxied,
            )
        except Exception as e:
            errors.append(f"{old_hostname}: failed to create DNS in {target_domain}: {e}")
            continue

        await _remove_synced_hostname_rows(
            db, new_hostname, keep_record_id=record.id, record_type=record.record_type
        )

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
