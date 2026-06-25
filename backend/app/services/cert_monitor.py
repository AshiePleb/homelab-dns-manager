"""Scheduled SSL certificate expiry checks for Caddy-managed hosts."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LogLevel, ProxyHost
from app.services.caddy_service import get_cert_expiry
from app.services.notification_service import send_notifications
from app.services.settings_service import get_setting, log_activity, set_setting

EXPIRY_ALERT_DAYS = 14


async def check_certificate_expiry(db: AsyncSession) -> dict:
    """Alert once per certificate expiry date when within the threshold."""
    result = await db.execute(
        select(ProxyHost).where(ProxyHost.enabled == True).order_by(ProxyHost.hostname)
    )
    hosts = result.scalars().all()
    checked = 0
    alerted = 0

    for host in hosts:
        expiry_info = get_cert_expiry(host.hostname)
        checked += 1
        if not expiry_info:
            continue

        days = expiry_info["days_remaining"]
        if days > EXPIRY_ALERT_DAYS:
            continue

        expiry_iso = expiry_info["expires_at"].date().isoformat()
        alert_key = f"ssl.alerted_expiry.{host.hostname}"
        last_alerted = await get_setting(db, alert_key)
        if last_alerted == expiry_iso:
            continue

        await send_notifications(
            db,
            "ssl_expiry",
            {
                "domain": host.hostname,
                "days": days,
                "expires_at": expiry_iso,
            },
        )
        await set_setting(db, alert_key, expiry_iso)
        await log_activity(
            db,
            "ssl",
            f"SSL certificate for {host.hostname} expires in {days} day(s) ({expiry_iso})",
            LogLevel.WARNING,
            details={"hostname": host.hostname, "days_remaining": days, "expires_at": expiry_iso},
        )
        alerted += 1

    return {"checked": checked, "alerted": alerted, "at": datetime.now(timezone.utc).isoformat()}
