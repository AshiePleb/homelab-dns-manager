"""Server-side session tracking with expiry and idle timeout."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import UserSession

settings = get_settings()


def _utcnow() -> datetime:
    """Naive UTC — SQLite returns naive datetimes; keep comparisons consistent."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def session_expires_at(now: datetime | None = None) -> datetime:
    base = now or _utcnow()
    return base + timedelta(minutes=settings.session_expire_minutes)


async def create_session(
    db: AsyncSession,
    *,
    user_id: int,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> UserSession:
    now = _utcnow()
    session = UserSession(
        id=str(uuid.uuid4()),
        user_id=user_id,
        expires_at=session_expires_at(now),
        last_seen_at=now,
        ip_address=ip_address,
        user_agent=(user_agent[:512] if user_agent else None),
    )
    db.add(session)
    await db.flush()
    return session


async def get_active_session(db: AsyncSession, session_id: str) -> UserSession | None:
    result = await db.execute(
        select(UserSession).where(
            UserSession.id == session_id,
            UserSession.revoked_at.is_(None),
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        return None

    now = _utcnow()
    idle_limit = timedelta(minutes=settings.session_idle_minutes)
    expires_at = _as_utc(session.expires_at)
    last_seen_at = _as_utc(session.last_seen_at)

    if expires_at is None or expires_at <= now:
        session.revoked_at = now
        await db.flush()
        return None

    if last_seen_at is None or last_seen_at + idle_limit <= now:
        session.revoked_at = now
        await db.flush()
        return None

    return session


async def touch_session(db: AsyncSession, session: UserSession) -> None:
    session.last_seen_at = _utcnow()
    await db.flush()


async def revoke_session(db: AsyncSession, session_id: str) -> None:
    result = await db.execute(select(UserSession).where(UserSession.id == session_id))
    session = result.scalar_one_or_none()
    if session and session.revoked_at is None:
        session.revoked_at = _utcnow()
        await db.flush()


async def revoke_user_sessions(
    db: AsyncSession,
    user_id: int,
    *,
    except_session_id: str | None = None,
) -> int:
    now = _utcnow()
    result = await db.execute(
        select(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
        )
    )
    count = 0
    for session in result.scalars().all():
        if except_session_id and session.id == except_session_id:
            continue
        session.revoked_at = now
        count += 1
    if count:
        await db.flush()
    return count


async def cleanup_expired_sessions(db: AsyncSession) -> int:
    now = _utcnow()
    idle_cutoff = now - timedelta(minutes=settings.session_idle_minutes)
    result = await db.execute(
        select(UserSession).where(UserSession.revoked_at.is_(None))
    )
    removed = 0
    for session in result.scalars().all():
        expires_at = _as_utc(session.expires_at)
        last_seen_at = _as_utc(session.last_seen_at)
        if (expires_at and expires_at <= now) or (last_seen_at and last_seen_at <= idle_cutoff):
            session.revoked_at = now
            removed += 1
    if removed:
        await db.flush()
    return removed


async def purge_old_sessions(db: AsyncSession, days: int = 30) -> int:
    cutoff = _utcnow() - timedelta(days=days)
    result = await db.execute(
        delete(UserSession).where(
            UserSession.revoked_at.is_not(None),
            UserSession.revoked_at < cutoff,
        )
    )
    await db.flush()
    return result.rowcount or 0
