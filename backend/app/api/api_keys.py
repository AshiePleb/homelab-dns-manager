from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import ApiKey, User
from app.schemas import ApiKeyCreate, ApiKeyCreatedResponse, ApiKeyResponse, ApiKeyUpdate
from app.core.deps import RequireAdmin
from app.services.api_key_service import create_api_key, list_api_keys

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


def _external_api_base(request: Request) -> str:
    return f"{request.url.scheme}://{request.url.netloc}/api/v1"


@router.get("/endpoint")
async def get_api_endpoint(request: Request, _: User = Depends(RequireAdmin)):
    return {
        "api_base": _external_api_base(request),
        "auth_header": "Authorization: Bearer <api_key>",
        "docs_note": "Use API keys for HomeLab WebHost Manager and other integrations.",
    }


@router.get("", response_model=list[ApiKeyResponse])
async def get_api_keys(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireAdmin),
):
    return await list_api_keys(db)


@router.post("", response_model=ApiKeyCreatedResponse)
async def create_key(
    data: ApiKeyCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireAdmin),
):
    row, full_key = await create_api_key(
        db,
        name=data.name,
        max_dns_records=data.max_dns_records,
        max_services=data.max_services,
        created_by=user.id,
    )
    usage = {"dns_records": 0, "services": 0}
    return ApiKeyCreatedResponse(
        id=row.id,
        name=row.name,
        key_prefix=row.key_prefix,
        max_dns_records=row.max_dns_records,
        max_services=row.max_services,
        is_active=row.is_active,
        usage=usage,
        last_used_at=row.last_used_at,
        created_at=row.created_at,
        api_key=full_key,
    )


@router.patch("/{key_id}", response_model=ApiKeyResponse)
async def update_key(
    key_id: int,
    data: ApiKeyUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireAdmin),
):
    from app.services.api_key_service import get_usage

    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="API key not found")
    if data.name is not None:
        row.name = data.name.strip()
    if data.max_dns_records is not None:
        row.max_dns_records = data.max_dns_records
    if data.max_services is not None:
        row.max_services = data.max_services
    if data.is_active is not None:
        row.is_active = data.is_active
    usage = await get_usage(db, row)
    return ApiKeyResponse(
        id=row.id,
        name=row.name,
        key_prefix=row.key_prefix,
        max_dns_records=row.max_dns_records,
        max_services=row.max_services,
        is_active=row.is_active,
        usage=usage,
        last_used_at=row.last_used_at,
        created_at=row.created_at,
    )


@router.delete("/{key_id}")
async def revoke_key(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireAdmin),
):
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="API key not found")
    row.is_active = False
    return {"message": "API key revoked"}
