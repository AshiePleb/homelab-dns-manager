"""Persist service health snapshots for history charts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import HealthCheckHistory
from app.services.health_service import get_services_health

RETENTION_DAYS = 30


async def record_health_snapshots(db: AsyncSession) -> int:
    rows = await get_services_health(db)
    now = datetime.now(timezone.utc)
    for row in rows:
        db.add(
            HealthCheckHistory(
                hostname=row["hostname"],
                overall=row["overall"],
                dns_ok=row["dns_ok"],
                port_ok=row["port_ok"],
                https_ok=row["https_ok"],
                ssl_days_remaining=row.get("ssl_days_remaining"),
                checked_at=now,
            )
        )
    cutoff = now - timedelta(days=RETENTION_DAYS)
    await db.execute(delete(HealthCheckHistory).where(HealthCheckHistory.checked_at < cutoff))
    await db.flush()
    return len(rows)


async def get_health_history(
    db: AsyncSession,
    hostname: str | None = None,
    hours: int = 24,
) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(hours=max(1, min(hours, 168)))
    q = select(HealthCheckHistory).where(HealthCheckHistory.checked_at >= since)
    if hostname:
        q = q.where(HealthCheckHistory.hostname == hostname)
    q = q.order_by(HealthCheckHistory.checked_at.asc())
    result = await db.execute(q)
    return [
        {
            "hostname": h.hostname,
            "overall": h.overall,
            "dns_ok": h.dns_ok,
            "port_ok": h.port_ok,
            "https_ok": h.https_ok,
            "ssl_days_remaining": h.ssl_days_remaining,
            "checked_at": h.checked_at,
        }
        for h in result.scalars().all()
    ]
