"""Startup bootstrap: Cloudflare token from .env + legacy DDNS domain import."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Domain, DNSRecord, LogLevel
from app.services.cloudflare_service import (
    get_cloudflare_service,
    sync_zones,
    update_cloudflare_record,
)
from app.services.ddns_service import get_public_ip, run_ddns_check
from app.services.settings_service import get_setting, set_setting, log_activity

settings = get_settings()


def _read_token_file(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8") as f:
            token = f.read().strip()
            return token or None
    except OSError:
        return None


def _parse_legacy_domains(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [d.strip().lower() for d in raw.split(",") if d.strip()]


def _zone_for_hostname(hostname: str, zones: list[Domain]) -> Domain | None:
    host = hostname.lower().rstrip(".")
    parts = host.split(".")
    for i in range(len(parts) - 1):
        candidate = ".".join(parts[i:])
        for zone in zones:
            if zone.name.lower() == candidate:
                return zone
    return None


async def bootstrap_cloudflare_token(db: AsyncSession) -> bool:
    """Load API token from env or secrets file into encrypted app settings."""
    existing = await get_setting(db, "cloudflare.api_token")
    if existing:
        return True

    token = settings.cloudflare_api_token
    if not token and settings.cloudflare_api_token_file:
        token = _read_token_file(settings.cloudflare_api_token_file)

    if not token:
        return False

    await set_setting(db, "cloudflare.api_token", token, encrypted=True)
    await log_activity(
        db,
        "cloudflare",
        "Cloudflare API token loaded from environment",
        LogLevel.SUCCESS,
    )
    return True


async def ensure_managed_ddns_hostname(
    db: AsyncSession,
    hostname: str,
    *,
    proxied: bool | None = None,
    current_ip: str | None = None,
) -> DNSRecord | None:
    """
    Register a hostname for dynamic DNS: link existing Cloudflare A record or create one.
    Called on startup (legacy import) and automatically when adding records in the dashboard.
    """
    cf = await get_cloudflare_service(db)
    if not cf:
        return None

    host = hostname.lower().strip()
    zones = await sync_zones(db)
    zone = _zone_for_hostname(host, zones)
    if not zone:
        await log_activity(
            db,
            "ddns",
            f"No Cloudflare zone found for {host}",
            LogLevel.WARNING,
        )
        return None

    use_proxied = settings.ddns_proxied_default if proxied is None else proxied
    ip = current_ip or await get_public_ip()

    result = await db.execute(
        select(DNSRecord).where(
            DNSRecord.domain_id == zone.id,
            DNSRecord.hostname == host,
            DNSRecord.record_type == "A",
        )
    )
    record = result.scalar_one_or_none()

    cf_records = await cf.list_records(zone.zone_id)
    cf_match = next(
        (r for r in cf_records if r["name"].lower() == host and r["type"] == "A"),
        None,
    )

    if record:
        record.managed = True
        record.app_created = True
        record.proxied = use_proxied
        if cf_match and not record.cloudflare_record_id:
            record.cloudflare_record_id = cf_match["id"]
        if record.cloudflare_record_id:
            await update_cloudflare_record(db, record, ip, reason="ddns_bootstrap")
        await db.flush()
        return record

    if cf_match:
        record = DNSRecord(
            domain_id=zone.id,
            cloudflare_record_id=cf_match["id"],
            hostname=host,
            record_type="A",
            content=cf_match["content"],
            proxied=use_proxied,
            managed=True,
            app_created=True,
            ttl=cf_match.get("ttl", 1),
        )
        db.add(record)
        await db.flush()
        await update_cloudflare_record(db, record, ip, reason="ddns_bootstrap")
        return record

    cf_rec = await cf.create_record(
        zone.zone_id,
        {
            "type": "A",
            "name": host,
            "content": ip,
            "ttl": 1,
            "proxied": use_proxied,
        },
    )
    record = DNSRecord(
        domain_id=zone.id,
        cloudflare_record_id=cf_rec["id"],
        hostname=host,
        record_type="A",
        content=ip,
        proxied=use_proxied,
        managed=True,
        app_created=True,
        ttl=1,
        last_updated_at=datetime.now(timezone.utc),
    )
    db.add(record)
    await db.flush()
    await log_activity(
        db,
        "ddns",
        f"Registered {host} for dynamic DNS updates",
        LogLevel.SUCCESS,
        details={"hostname": host, "ip": ip},
    )
    return record


async def import_legacy_ddns_domains(db: AsyncSession) -> list[str]:
    """Import hostnames from favonia-style DOMAINS= env (one-time / idempotent)."""
    domains = _parse_legacy_domains(settings.legacy_ddns_domains)
    if not domains:
        return []

    zones = await sync_zones(db)
    zone_names = {z.name.lower() for z in zones}

    imported: list[str] = []
    for host in domains:
        host_l = host.lower().rstrip(".")
        if host_l in zone_names or host_l in {f"www.{z}" for z in zone_names}:
            await log_activity(
                db,
                "ddns",
                f"Skipped {host} — apex/www must stay on your main site host (use Services for subdomains)",
                LogLevel.WARNING,
            )
            continue
        record = await ensure_managed_ddns_hostname(db, host)
        if record:
            imported.append(host)

    if imported:
        await log_activity(
            db,
            "ddns",
            f"Imported {len(imported)} hostname(s) from legacy DDNS config",
            LogLevel.SUCCESS,
            details={"hostnames": imported},
        )
        from app.services.service_provision import infer_default_zone_from_hostnames
        zone = await infer_default_zone_from_hostnames(imported)
        if zone and not await get_setting(db, "general.default_zone"):
            from app.services.service_provision import set_default_zone
            await set_default_zone(db, zone)
    return imported


async def run_startup_bootstrap(db: AsyncSession) -> None:
    """Configure Cloudflare from secrets, import legacy domains, run initial IP sync."""
    has_token = await bootstrap_cloudflare_token(db)
    if not has_token:
        return

    await import_legacy_ddns_domains(db)

    try:
        await run_ddns_check(db)
    except Exception as e:
        await log_activity(
            db,
            "ddns",
            f"Initial DDNS sync skipped: {e}",
            LogLevel.WARNING,
        )
