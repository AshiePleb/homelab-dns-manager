"""API key management and per-key resource limits."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_api_key, verify_api_key
from app.models import ApiKey, DNSRecord, ProxyHost


async def get_api_key_by_token(db: AsyncSession, token: str) -> ApiKey | None:
    if len(token) < 16:
        return None
    prefix = token[:12]
    result = await db.execute(
        select(ApiKey).where(ApiKey.key_prefix == prefix, ApiKey.is_active.is_(True))
    )
    for key in result.scalars().all():
        if verify_api_key(token, key.key_hash):
            key.last_used_at = datetime.now(timezone.utc)
            return key
    return None


async def count_dns_records(db: AsyncSession, api_key_id: int) -> int:
    return int(
        await db.scalar(
            select(func.count()).select_from(DNSRecord).where(DNSRecord.api_key_id == api_key_id)
        )
        or 0
    )


async def count_services(db: AsyncSession, api_key_id: int) -> int:
    return int(
        await db.scalar(
            select(func.count()).select_from(ProxyHost).where(ProxyHost.api_key_id == api_key_id)
        )
        or 0
    )


async def get_usage(db: AsyncSession, api_key: ApiKey) -> dict:
    return {
        "dns_records": await count_dns_records(db, api_key.id),
        "services": await count_services(db, api_key.id),
    }


async def ensure_dns_limit(db: AsyncSession, api_key: ApiKey, *, adding: int = 1) -> None:
    usage = await count_dns_records(db, api_key.id)
    if usage + adding > api_key.max_dns_records:
        raise ValueError(
            f"DNS record limit reached ({usage}/{api_key.max_dns_records}). "
            "Increase the limit on this API key or delete unused records."
        )


async def ensure_service_limit(db: AsyncSession, api_key: ApiKey, *, adding: int = 1) -> None:
    usage = await count_services(db, api_key.id)
    if usage + adding > api_key.max_services:
        raise ValueError(
            f"Service limit reached ({usage}/{api_key.max_services}). "
            "Increase the limit on this API key or delete unused services."
        )


async def create_api_key(
    db: AsyncSession,
    *,
    name: str,
    max_dns_records: int,
    max_services: int,
    created_by: int | None,
) -> tuple[ApiKey, str]:
    full_key, prefix, key_hash = generate_api_key()
    row = ApiKey(
        name=name.strip(),
        key_prefix=prefix,
        key_hash=key_hash,
        max_dns_records=max_dns_records,
        max_services=max_services,
        created_by=created_by,
    )
    db.add(row)
    await db.flush()
    return row, full_key


async def list_api_keys(db: AsyncSession) -> list[dict]:
    result = await db.execute(select(ApiKey).order_by(ApiKey.created_at.desc()))
    rows = []
    for key in result.scalars().all():
        usage = await get_usage(db, key)
        rows.append(
            {
                "id": key.id,
                "name": key.name,
                "key_prefix": key.key_prefix,
                "max_dns_records": key.max_dns_records,
                "max_services": key.max_services,
                "is_active": key.is_active,
                "usage": usage,
                "last_used_at": key.last_used_at,
                "created_at": key.created_at,
            }
        )
    return rows
