import httpx
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DNSRecord, IPChangeLog, LogLevel
from app.services.cloudflare_service import update_cloudflare_record
from app.services.settings_service import get_setting, log_activity
from app.config import get_settings
from sqlalchemy.orm import selectinload

settings = get_settings()

_current_ip: str | None = None
_last_check: datetime | None = None


def _is_main_site_hostname(hostname: str, zone_name: str | None) -> bool:
    """Apex and www are never auto-updated — protects external main website hosting."""
    if not zone_name:
        return False
    host = hostname.lower().rstrip(".")
    zone = zone_name.lower()
    return host == zone or host == f"www.{zone}"


async def _ddns_eligible_records(db: AsyncSession) -> list[DNSRecord]:
    result = await db.execute(
        select(DNSRecord)
        .options(selectinload(DNSRecord.domain))
        .where(DNSRecord.managed == True, DNSRecord.record_type == "A")
    )
    return [
        r
        for r in result.scalars().all()
        if not _is_main_site_hostname(r.hostname, r.domain.name if r.domain else None)
    ]


async def get_public_ip() -> str:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(settings.public_ip_check_url)
        resp.raise_for_status()
        return resp.text.strip()


async def get_stored_ip(db: AsyncSession) -> str | None:
    return await get_setting(db, "ddns.current_ip")


async def set_stored_ip(db: AsyncSession, ip: str) -> None:
    from app.services.settings_service import set_setting
    await set_setting(db, "ddns.current_ip", ip)


async def get_managed_hostnames(db: AsyncSession) -> list[dict]:
    records = await _ddns_eligible_records(db)
    return [
        {
            "id": r.id,
            "hostname": r.hostname,
            "content": r.content,
            "proxied": r.proxied,
            "last_updated_at": r.last_updated_at.isoformat() if r.last_updated_at else None,
        }
        for r in records
    ]


def _parse_last_check(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


async def _persist_last_check(db: AsyncSession, when: datetime) -> None:
    from app.services.settings_service import set_setting

    await set_setting(db, "ddns.last_check_at", when.isoformat())


async def get_ddns_status(db: AsyncSession) -> dict:
    from sqlalchemy import desc

    result = await db.execute(
        select(IPChangeLog).order_by(desc(IPChangeLog.created_at)).limit(1)
    )
    last_change_log = result.scalar_one_or_none()
    stored = await get_stored_ip(db)
    managed = await get_managed_hostnames(db)
    interval_minutes = int(
        await get_setting(db, "general.refresh_interval") or settings.ddns_interval_minutes
    )
    last_check = _parse_last_check(await get_setting(db, "ddns.last_check_at")) or _last_check
    next_check = None
    if last_check:
        next_check = last_check + timedelta(minutes=interval_minutes)
    return {
        "current_ip": stored or _current_ip,
        "last_check": last_check,
        "next_check": next_check,
        "last_change": last_change_log.created_at if last_change_log else None,
        "interval_minutes": interval_minutes,
        "is_running": True,
        "managed_hostnames": [m["hostname"] for m in managed],
        "managed_count": len(managed),
    }


async def run_ddns_check(db: AsyncSession) -> dict | None:
    global _current_ip, _last_check
    now = datetime.now(timezone.utc)
    _last_check = now
    await _persist_last_check(db, now)

    try:
        new_ip = await get_public_ip()
        _current_ip = new_ip
    except Exception as e:
        await log_activity(
            db, "ddns", f"Failed to fetch public IP: {e}", LogLevel.ERROR
        )
        return None

    old_ip = await get_stored_ip(db)
    if old_ip == new_ip:
        return {"changed": False, "ip": new_ip, "checked_at": now.isoformat()}

    managed_records = await _ddns_eligible_records(db)
    affected = []

    for record in managed_records:
        try:
            await update_cloudflare_record(db, record, new_ip, reason="ddns")
            affected.append({"id": record.id, "hostname": record.hostname})
        except Exception as e:
            await log_activity(
                db,
                "ddns",
                f"Failed to update {record.hostname}: {e}",
                LogLevel.ERROR,
            )
            from app.services.notification_service import send_notifications
            await send_notifications(
                db, "cf_failure", {"message": f"{record.hostname}: {e}"}
            )

    change_log = IPChangeLog(
        old_ip=old_ip,
        new_ip=new_ip,
        affected_records={"records": affected},
    )
    db.add(change_log)
    await set_stored_ip(db, new_ip)

    await log_activity(
        db,
        "ddns",
        f"Public IP changed from {old_ip or 'unknown'} to {new_ip} ({len(affected)} record(s))",
        LogLevel.SUCCESS,
        details={"old_ip": old_ip, "new_ip": new_ip, "affected": affected},
    )

    from app.services.notification_service import send_notifications
    await send_notifications(
        db, "ip_change", {"old_ip": old_ip, "new_ip": new_ip, "affected": affected}
    )

    return {"changed": True, "old_ip": old_ip, "new_ip": new_ip, "affected": affected}
