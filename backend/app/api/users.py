from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, LogLevel
from app.schemas import UserCreate, UserResponse, UserUpdate
from app.core.security import hash_password
from app.core.deps import RequireAdmin
from app.services.session_service import revoke_user_sessions
from app.services.settings_service import log_activity
from app.services.notification_service import send_notifications

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireAdmin),
):
    result = await db.execute(select(User).order_by(User.username))
    return result.scalars().all()


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(RequireAdmin),
):
    existing = await db.execute(select(User).where(User.username == data.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already exists")
    user = User(
        username=data.username,
        name=data.name,
        email=data.email,
        role=data.role,
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    await db.flush()
    await log_activity(
        db, "users", f"Created user {user.username}", LogLevel.SUCCESS,
        details={"username": user.username, "role": user.role.value}, user_id=admin.id,
    )
    await send_notifications(db, "user_changed", {"action": "created", "username": user.username})
    return user


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(RequireAdmin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if data.username is not None and data.username != user.username:
        taken = await db.execute(select(User).where(User.username == data.username))
        if taken.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Username already exists")
        user.username = data.username
    if data.name is not None:
        user.name = data.name or None
    if data.email is not None:
        user.email = data.email
    if data.role is not None:
        if user_id == current.id and data.role != user.role:
            raise HTTPException(status_code=400, detail="Cannot change your own role")
        user.role = data.role
    if data.is_active is not None:
        if user_id == current.id and not data.is_active:
            raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
        if data.is_active is False and user.is_active:
            await revoke_user_sessions(db, user.id)
        user.is_active = data.is_active
    if data.password:
        user.hashed_password = hash_password(data.password)
        user.must_change_credentials = False
        await revoke_user_sessions(db, user.id)
    await db.flush()
    await log_activity(
        db, "users", f"Updated user {user.username}", LogLevel.INFO,
        details={"username": user.username}, user_id=current.id,
    )
    await send_notifications(db, "user_changed", {"action": "updated", "username": user.username})
    return user


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(RequireAdmin),
):
    if user_id == current.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    username = user.username
    await db.delete(user)
    await log_activity(
        db, "users", f"Deleted user {username}", LogLevel.WARNING,
        details={"username": username}, user_id=current.id,
    )
    await send_notifications(db, "user_changed", {"action": "deleted", "username": username})
    return {"message": "User deleted"}
