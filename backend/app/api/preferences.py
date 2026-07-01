from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.security import verify_password
from app.database import get_db
from app.models import User
from app.schemas import (
    UserPreferences,
    UserPreferencesUpdate,
    UserResponse,
    TotpSetupResponse,
    TotpEnableRequest,
    TotpDisableRequest,
)
from app.services.user_preferences import get_user_preferences, apply_user_preferences
from app.services.totp_service import (
    generate_totp_secret,
    get_provisioning_uri,
    verify_totp,
    store_totp_secret,
    read_totp_secret,
)

router = APIRouter(prefix="/auth", tags=["preferences"])


def build_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        name=user.name,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        must_change_credentials=user.must_change_credentials,
        totp_enabled=user.totp_enabled,
        preferences=UserPreferences(**get_user_preferences(user)),
        created_at=user.created_at,
    )


@router.get("/preferences", response_model=UserPreferences)
async def get_preferences(user: User = Depends(get_current_user)):
    return UserPreferences(**get_user_preferences(user))


@router.patch("/preferences", response_model=UserPreferences)
async def update_preferences(
    data: UserPreferencesUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prefs = apply_user_preferences(user, data.model_dump(exclude_unset=True))
    await db.flush()
    return UserPreferences(**prefs)


@router.post("/2fa/setup", response_model=TotpSetupResponse)
async def setup_2fa(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.totp_enabled:
        raise HTTPException(status_code=400, detail="2FA is already enabled")
    secret = generate_totp_secret()
    user.totp_secret = store_totp_secret(secret)
    await db.flush()
    return TotpSetupResponse(
        secret=secret,
        provisioning_uri=get_provisioning_uri(secret, user.username),
    )


@router.post("/2fa/enable")
async def enable_2fa(
    data: TotpEnableRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    secret = read_totp_secret(user.totp_secret)
    if not secret or not verify_totp(secret, data.code):
        raise HTTPException(status_code=400, detail="Invalid verification code")
    user.totp_enabled = True
    await db.flush()
    return {"message": "Two-factor authentication enabled"}


@router.post("/2fa/disable")
async def disable_2fa(
    data: TotpDisableRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Password incorrect")
    secret = read_totp_secret(user.totp_secret)
    if not secret or not verify_totp(secret, data.code):
        raise HTTPException(status_code=400, detail="Invalid verification code")
    user.totp_enabled = False
    user.totp_secret = None
    await db.flush()
    return {"message": "Two-factor authentication disabled"}
