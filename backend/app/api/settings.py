from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, LogLevel
from app.schemas import (
    CloudflareSettings,
    NPMSettings,
    NotificationSettings,
    NotificationSettingsView,
    GeneralSettings,
    SettingsResponse,
)
from app.core.deps import RequireAdmin, RequireViewer
from app.services.settings_service import get_setting, set_setting, get_settings_dict, log_activity
from app.services.service_provision import get_default_zone, set_default_zone
from app.services.notification_service import send_notifications, EVENT_DEFAULTS
from sqlalchemy import select
from app.models import Domain

router = APIRouter(prefix="/settings", tags=["settings"])


def _bool_cfg(cfg: dict, key: str, default: str = "false") -> bool:
    return cfg.get(key, default) == "true"


def _notification_view(cfg: dict) -> NotificationSettingsView:
    return NotificationSettingsView(
        discord_webhook_configured=bool(cfg.get("discord_webhook")),
        discord_format=(cfg.get("discord_format") or "embed").strip().lower()
        if (cfg.get("discord_format") or "embed").strip().lower() in ("plain", "embed")
        else "embed",
        discord_username=cfg.get("discord_username") or None,
        discord_accent_color=cfg.get("discord_accent_color") or "#5865F2",
        smtp_password_configured=bool(cfg.get("smtp_password")),
        smtp_host=cfg.get("smtp_host") or None,
        smtp_port=int(cfg.get("smtp_port") or "587"),
        smtp_username=cfg.get("smtp_username") or None,
        smtp_from=cfg.get("smtp_from") or None,
        smtp_to=cfg.get("smtp_to") or None,
        notify_ip_change=_bool_cfg(cfg, "notify_ip_change", EVENT_DEFAULTS["ip_change"]),
        notify_cf_failure=_bool_cfg(cfg, "notify_cf_failure", EVENT_DEFAULTS["cf_failure"]),
        notify_service_created=_bool_cfg(cfg, "notify_service_created", EVENT_DEFAULTS["service_created"]),
        notify_service_deleted=_bool_cfg(cfg, "notify_service_deleted", EVENT_DEFAULTS["service_deleted"]),
        notify_service_updated=_bool_cfg(cfg, "notify_service_updated", EVENT_DEFAULTS["service_updated"]),
        notify_record_created=_bool_cfg(cfg, "notify_record_created", EVENT_DEFAULTS["record_created"]),
        notify_record_deleted=_bool_cfg(cfg, "notify_record_deleted", EVENT_DEFAULTS["record_deleted"]),
        notify_record_updated=_bool_cfg(cfg, "notify_record_updated", EVENT_DEFAULTS["record_updated"]),
        notify_ssl_expiry=_bool_cfg(cfg, "notify_ssl_expiry", EVENT_DEFAULTS["ssl_expiry"]),
        notify_ssl_renewed=_bool_cfg(cfg, "notify_ssl_renewed", EVENT_DEFAULTS["ssl_renewed"]),
        notify_app_update=_bool_cfg(cfg, "notify_app_update", EVENT_DEFAULTS["app_update"]),
        notify_zone_synced=_bool_cfg(cfg, "notify_zone_synced", EVENT_DEFAULTS["zone_synced"]),
        notify_domain_migrated=_bool_cfg(cfg, "notify_domain_migrated", EVENT_DEFAULTS["domain_migrated"]),
        notify_login_failed=_bool_cfg(cfg, "notify_login_failed", EVENT_DEFAULTS["login_failed"]),
        notify_user_changed=_bool_cfg(cfg, "notify_user_changed", EVENT_DEFAULTS["user_changed"]),
        notify_api_key_changed=_bool_cfg(cfg, "notify_api_key_changed", EVENT_DEFAULTS["api_key_changed"]),
        notify_settings_changed=_bool_cfg(cfg, "notify_settings_changed", EVENT_DEFAULTS["settings_changed"]),
        notify_backup_restored=_bool_cfg(cfg, "notify_backup_restored", EVENT_DEFAULTS["backup_restored"]),
    )


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
    user: User = Depends(RequireAdmin),
):
    await set_setting(db, "general.timezone", data.timezone)
    await set_setting(db, "general.refresh_interval", str(data.refresh_interval))
    await set_setting(db, "general.theme", data.theme)
    if data.default_zone:
        await set_default_zone(db, data.default_zone)
    await log_activity(
        db, "settings", "Updated general settings", LogLevel.INFO,
        details={"section": "general"}, user_id=user.id,
    )
    await send_notifications(db, "settings_changed", {"section": "general"})
    return {"message": "General settings updated"}


@router.put("/cloudflare")
async def update_cloudflare(
    data: CloudflareSettings,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireAdmin),
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
    await log_activity(
        db, "settings", "Updated Cloudflare settings", LogLevel.INFO,
        details={"section": "cloudflare", "token_updated": bool(data.api_token)},
        user_id=user.id,
    )
    await send_notifications(db, "settings_changed", {"section": "cloudflare"})
    return {"message": "Cloudflare settings updated"}


@router.put("/npm")
async def update_npm(
    data: NPMSettings,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireAdmin),
):
    if data.url:
        await set_setting(db, "npm.url", data.url)
    if data.username:
        await set_setting(db, "npm.username", data.username)
    if data.password:
        await set_setting(db, "npm.password", data.password, encrypted=True)
    await log_activity(
        db, "settings", "Updated NPM settings", LogLevel.INFO,
        details={"section": "npm"}, user_id=user.id,
    )
    await send_notifications(db, "settings_changed", {"section": "npm"})
    return {"message": "NPM settings updated"}


@router.get("/notifications", response_model=NotificationSettingsView)
async def get_notifications(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireAdmin),
):
    cfg = await get_settings_dict(db, "notify.")
    return _notification_view(cfg)


@router.put("/notifications")
async def update_notifications(
    data: NotificationSettings,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireAdmin),
):
    fmt = (data.discord_format or "embed").strip().lower()
    if fmt not in ("plain", "embed"):
        fmt = "embed"
    accent = (data.discord_accent_color or "#5865F2").strip()
    if not accent.startswith("#"):
        accent = f"#{accent}"

    fields = {
        "notify.discord_webhook": (data.discord_webhook, True),
        "notify.discord_format": (fmt, False),
        "notify.discord_username": (data.discord_username, False),
        "notify.discord_accent_color": (accent, False),
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
        "notify.notify_service_updated": (str(data.notify_service_updated).lower(), False),
        "notify.notify_record_created": (str(data.notify_record_created).lower(), False),
        "notify.notify_record_deleted": (str(data.notify_record_deleted).lower(), False),
        "notify.notify_record_updated": (str(data.notify_record_updated).lower(), False),
        "notify.notify_ssl_expiry": (str(data.notify_ssl_expiry).lower(), False),
        "notify.notify_ssl_renewed": (str(data.notify_ssl_renewed).lower(), False),
        "notify.notify_app_update": (str(data.notify_app_update).lower(), False),
        "notify.notify_zone_synced": (str(data.notify_zone_synced).lower(), False),
        "notify.notify_domain_migrated": (str(data.notify_domain_migrated).lower(), False),
        "notify.notify_login_failed": (str(data.notify_login_failed).lower(), False),
        "notify.notify_user_changed": (str(data.notify_user_changed).lower(), False),
        "notify.notify_api_key_changed": (str(data.notify_api_key_changed).lower(), False),
        "notify.notify_settings_changed": (str(data.notify_settings_changed).lower(), False),
        "notify.notify_backup_restored": (str(data.notify_backup_restored).lower(), False),
    }
    for key, (value, encrypted) in fields.items():
        if value is None:
            continue
        if encrypted and value == "":
            await set_setting(db, key, None, encrypted=False)
            continue
        await set_setting(db, key, value, encrypted=encrypted)

    await log_activity(
        db, "settings", "Updated notification settings", LogLevel.INFO,
        details={"section": "notifications", "discord_format": fmt},
        user_id=user.id,
    )
    await send_notifications(db, "settings_changed", {"section": "notifications"})
    return {"message": "Notification settings updated"}


@router.get("/zones")
async def list_zone_names(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireViewer),
):
    result = await db.execute(select(Domain).order_by(Domain.name))
    return [d.name for d in result.scalars().all()]
