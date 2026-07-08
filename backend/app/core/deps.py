from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, UserRole, ApiKey
from app.core.security import decode_access_token, is_api_key_token
from app.services.session_service import get_active_session, touch_session
from app.services.api_key_service import get_api_key_by_token

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired — please sign in again",
        )
    username = payload.get("sub")
    session_id = payload.get("sid")
    if not username or not session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    session = await get_active_session(db, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired — please sign in again",
        )

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not user.is_active or user.id != session.user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    await touch_session(db, session)
    return user


def require_role(*roles: UserRole):
    async def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles and user.role != UserRole.ADMIN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return checker


RequireAdmin = require_role(UserRole.ADMIN)
RequireOperator = require_role(UserRole.ADMIN, UserRole.OPERATOR)
RequireViewer = require_role(UserRole.ADMIN, UserRole.OPERATOR, UserRole.VIEWER)


async def get_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> ApiKey:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key required")
    token = credentials.credentials
    if not is_api_key_token(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    api_key = await get_api_key_by_token(db, token)
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked API key")
    return api_key
