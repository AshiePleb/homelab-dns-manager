from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.schemas import (
    CloudflareSettings,
    NPMSettings,
    NotificationSettings,
    NotificationSettingsView,
    GeneralSettings,
    SettingsResponse,
)
from app.core.deps import RequireAdmin, RequireViewer
from app.services.settings_service import get_setting, set_setting, get_settings_dict
from app.services.service_provision import get_default_zone, set_default_zone
from sqlalchemy import select
from app.models import Domain

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
async def get_all_settings(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireViewer),
):
    default_zone = await get_default_zone(db)
    general = GeneralSettings(
        timezone=await get_setting(db, "general.timezone") or "UTC",
        refresh_interval=int(await get_setting(db, "general.refresh_interval") or "5"),
        theme=await get_setting(db, "general.theme") or "midnight",
        default_zone=default_zone,
    )
    return SettingsResponse(
        general=general,
        cloudflare_configured=bool(await get_setting(db, "cloudflare.api_token")),
        npm_configured=bool(await get_setting(db, "npm.url")),
        notifications_configured=bool(await get_setting(db, "notify.discord_webhook")),
        default_zone=default_zone,
    )


@router.put("/general")
async def update_general(
    data: GeneralSettings,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireAdmin),
):
    await set_setting(db, "general.timezone", data.timezone)
    await set_setting(db, "general.refresh_interval", str(data.refresh_interval))
    await set_setting(db, "general.theme", data.theme)
    if data.default_zone:
        await set_default_zone(db, data.default_zone)
    return {"message": "General settings updated"}


@router.put("/cloudflare")
async def update_cloudflare(
    data: CloudflareSettings,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireAdmin),
):
    updated = False
    if data.api_token:
        await set_setting(db, "cloudflare.api_token", data.api_token, encrypted=True)
        updated = True
    if data.account_id:
        await set_setting(db, "cloudflare.account_id", data.account_id)
        updated = True
    if not updated:
        return {"message": "No changes — leave token blank to keep existing, or use Test Connection"}
    return {"message": "Cloudflare settings updated"}


@router.put("/npm")
async def update_npm(
    data: NPMSettings,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireAdmin),
):
    if data.url:
        await set_setting(db, "npm.url", data.url)
    if data.username:
        await set_setting(db, "npm.username", data.username)
    if data.password:
        await set_setting(db, "npm.password", data.password, encrypted=True)
    return {"message": "NPM settings updated"}


@router.get("/notifications", response_model=NotificationSettingsView)
async def get_notifications(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireAdmin),
):
    cfg = await get_settings_dict(db, "notify.")
    return NotificationSettingsView(
        discord_webhook_configured=bool(cfg.get("discord_webhook")),
        smtp_password_configured=bool(cfg.get("smtp_password")),
        smtp_host=cfg.get("smtp_host") or None,
        smtp_port=int(cfg.get("smtp_port") or "587"),
        smtp_username=cfg.get("smtp_username") or None,
        smtp_from=cfg.get("smtp_from") or None,
        smtp_to=cfg.get("smtp_to") or None,
        notify_ip_change=cfg.get("notify_ip_change", "true") == "true",
        notify_cf_failure=cfg.get("notify_cf_failure", "true") == "true",
        notify_service_created=cfg.get("notify_service_created", "true") == "true",
        notify_service_deleted=cfg.get("notify_service_deleted", "false") == "true",
        notify_record_created=cfg.get("notify_record_created", "true") == "true",
        notify_record_deleted=cfg.get("notify_record_deleted", "false") == "true",
        notify_ssl_expiry=cfg.get("notify_ssl_expiry", "true") == "true",
    )


@router.put("/notifications")
async def update_notifications(
    data: NotificationSettings,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireAdmin),
):
    fields = {
        "notify.discord_webhook": (data.discord_webhook, True),
        "notify.smtp_host": (data.smtp_host, False),
        "notify.smtp_port": (str(data.smtp_port), False),
        "notify.smtp_username": (data.smtp_username, False),
        "notify.smtp_password": (data.smtp_password, True),
        "notify.smtp_from": (data.smtp_from, False),
        "notify.smtp_to": (data.smtp_to, False),
        "notify.notify_ip_change": (str(data.notify_ip_change).lower(), False),
        "notify.notify_cf_failure": (str(data.notify_cf_failure).lower(), False),
        "notify.notify_service_created": (str(data.notify_service_created).lower(), False),
        "notify.notify_service_deleted": (str(data.notify_service_deleted).lower(), False),
        "notify.notify_record_created": (str(data.notify_record_created).lower(), False),
        "notify.notify_record_deleted": (str(data.notify_record_deleted).lower(), False),
        "notify.notify_ssl_expiry": (str(data.notify_ssl_expiry).lower(), False),
    }
    for key, (value, encrypted) in fields.items():
        if value is None:
            continue
        if encrypted and value == "":
            await set_setting(db, key, None, encrypted=False)
            continue
        await set_setting(db, key, value, encrypted=encrypted)
    return {"message": "Notification settings updated"}


@router.get("/zones")
async def list_zone_names(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireViewer),
):
    result = await db.execute(select(Domain).order_by(Domain.name))
    return [d.name for d in result.scalars().all()]
