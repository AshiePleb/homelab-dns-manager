from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.schemas import Token, LoginRequest, UserResponse, PasswordChange, OnboardingRequest, ProfileUpdate, ProfileUpdateResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.security import verify_password, hash_password, create_access_token, password_needs_rehash, decode_access_token
from app.core.deps import get_current_user
from app.core.rate_limit import limiter
from app.services.session_service import (
    create_session,
    revoke_session,
    revoke_user_sessions,
)

router = APIRouter(prefix="/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


@router.post("/login", response_model=Token)
@limiter.limit("10/minute")
async def login(
    request: Request,
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.username == data.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    if password_needs_rehash(user.hashed_password):
        user.hashed_password = hash_password(data.password)

    session = await create_session(
        db,
        user_id=user.id,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    token = create_access_token(
        {"sub": user.username, "role": user.role.value},
        session_id=session.id,
    )
    return Token(access_token=token, expires_at=session.expires_at)


@router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    if credentials:
        payload = decode_access_token(credentials.credentials)
        if payload and payload.get("sid"):
            await revoke_session(db, payload["sid"])
    return {"message": "Signed out"}


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return user


@router.post("/onboarding", response_model=UserResponse)
async def complete_onboarding(
    data: OnboardingRequest,
    user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    if not user.must_change_credentials:
        raise HTTPException(status_code=400, detail="Onboarding already completed")
    if not verify_password(data.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password incorrect")

    user.name = data.name.strip()
    user.email = data.email
    user.hashed_password = hash_password(data.new_password)
    user.must_change_credentials = False
    session_id = None
    if credentials:
        payload = decode_access_token(credentials.credentials)
        session_id = payload.get("sid") if payload else None
    await revoke_user_sessions(db, user.id, except_session_id=session_id)
    await db.flush()
    return user


@router.post("/change-password")
async def change_password(
    data: PasswordChange,
    user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(data.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password incorrect")
    user.hashed_password = hash_password(data.new_password)
    session_id = None
    if credentials:
        payload = decode_access_token(credentials.credentials)
        session_id = payload.get("sid") if payload else None
    await revoke_user_sessions(db, user.id, except_session_id=session_id)
    await db.flush()
    return {"message": "Password updated"}


@router.patch("/profile", response_model=ProfileUpdateResponse)
async def update_profile(
    data: ProfileUpdate,
    user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    username_changed = False
    if data.username and data.username != user.username:
        if not data.current_password or not verify_password(data.current_password, user.hashed_password):
            raise HTTPException(status_code=400, detail="Current password required to change username")
        existing = await db.execute(select(User).where(User.username == data.username))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Username already taken")
        user.username = data.username.strip()
        username_changed = True

    if data.name is not None:
        user.name = data.name.strip()
    if data.email is not None:
        user.email = data.email

    await db.flush()

    new_token = None
    if username_changed:
        session_id = ""
        if credentials:
            payload = decode_access_token(credentials.credentials)
            session_id = payload.get("sid", "") if payload else ""
        new_token = create_access_token(
            {"sub": user.username, "role": user.role.value},
            session_id=session_id,
        )

    return ProfileUpdateResponse(user=user, access_token=new_token)
