from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import RequireViewer, RequireAdmin
from app.database import get_db
from app.models import User, LogLevel
from app.schemas import VersionStatusResponse, AppUpdateResponse
from app.services.version_service import get_version_status
from app.services.update_service import start_app_update
from app.services.settings_service import log_activity

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/version", response_model=VersionStatusResponse)
async def version_status(_: User = Depends(RequireViewer)):
    return await get_version_status()


@router.post("/update", response_model=AppUpdateResponse)
async def update_app(
    force: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireAdmin),
):
    """Pull the latest Docker image and recreate this container (brief downtime)."""
    try:
        result = await start_app_update(force=force)
        await log_activity(
            db,
            "system",
            f"App update started → {result.get('target_version') or result.get('image')}",
            LogLevel.INFO,
            details=result,
            user_id=user.id,
        )
        await db.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
