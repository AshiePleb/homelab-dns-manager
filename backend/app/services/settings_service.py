from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cryptography.fernet import InvalidToken

from app.models import AppSetting, ActivityLog, LogLevel
from app.core.security import encrypt_value, decrypt_value


def _read_setting_value(setting: AppSetting) -> str | None:
    if not setting.value:
        return None
    if not setting.encrypted:
        return setting.value
    try:
        return decrypt_value(setting.value)
    except InvalidToken:
        return None


async def get_setting(db: AsyncSession, key: str, default: str | None = None) -> str | None:
    result = await db.execute(select(AppSetting).where(AppSetting.key == key))
    setting = result.scalar_one_or_none()
    if not setting:
        return default
    value = _read_setting_value(setting)
    return value if value is not None else default


async def set_setting(
    db: AsyncSession, key: str, value: str | None, encrypted: bool = False
) -> None:
    result = await db.execute(select(AppSetting).where(AppSetting.key == key))
    setting = result.scalar_one_or_none()

    # Never persist encrypted empty secrets (causes decrypt errors on read).
    if not value:
        if setting:
            setting.value = None
            setting.encrypted = False
        else:
            db.add(AppSetting(key=key, value=None, encrypted=False))
        await db.flush()
        return

    stored = encrypt_value(value) if encrypted else value
    if setting:
        setting.value = stored
        setting.encrypted = encrypted
    else:
        db.add(AppSetting(key=key, value=stored, encrypted=encrypted))
    await db.flush()


async def get_settings_dict(db: AsyncSession, prefix: str) -> dict[str, str]:
    result = await db.execute(
        select(AppSetting).where(AppSetting.key.startswith(prefix))
    )
    settings = {}
    for s in result.scalars().all():
        key = s.key.removeprefix(prefix)
        value = _read_setting_value(s)
        if value is not None:
            settings[key] = value
    return settings


async def log_activity(
    db: AsyncSession,
    category: str,
    message: str,
    level: LogLevel = LogLevel.INFO,
    details: dict | None = None,
    user_id: int | None = None,
) -> ActivityLog:
    log = ActivityLog(
        category=category,
        message=message,
        level=level,
        details=details,
        user_id=user_id,
    )
    db.add(log)
    await db.flush()
    return log


async def serialize_activity_logs(db: AsyncSession, logs: list[ActivityLog]) -> list[dict]:
    """Attach username for UI without N+1 when few distinct actors."""
    from app.models import User

    user_ids = {log.user_id for log in logs if log.user_id}
    usernames: dict[int, str] = {}
    if user_ids:
        result = await db.execute(select(User).where(User.id.in_(user_ids)))
        for u in result.scalars().all():
            usernames[u.id] = u.username
    return [
        {
            "id": log.id,
            "level": log.level,
            "category": log.category,
            "message": log.message,
            "details": log.details,
            "user_id": log.user_id,
            "username": usernames.get(log.user_id) if log.user_id else None,
            "created_at": log.created_at,
        }
        for log in logs
    ]
