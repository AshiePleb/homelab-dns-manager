from fastapi import APIRouter, Depends, HTTPException

from app.models import User, LogLevel
from app.schemas import ContainerResponse
from app.core.deps import RequireViewer, RequireOperator
from app.services.docker_service import (
    list_containers,
    container_action,
    get_container_logs,
    get_container_details,
)
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.settings_service import log_activity

router = APIRouter(prefix="/docker", tags=["docker"])


@router.get("/containers", response_model=list[ContainerResponse])
async def get_containers(_: User = Depends(RequireViewer)):
    return list_containers()


@router.post("/containers/{container_id}/{action}")
async def do_container_action(
    container_id: str,
    action: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireOperator),
):
    if action not in ("start", "stop", "restart"):
        raise HTTPException(status_code=400, detail="Invalid action")
    try:
        result = container_action(container_id, action)
        await log_activity(
            db,
            "docker",
            f"Container {container_id} {action}ed",
            LogLevel.INFO,
            user_id=user.id,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/containers/{container_id}/logs")
async def container_logs(
    container_id: str,
    tail: int = 100,
    _: User = Depends(RequireViewer),
):
    try:
        return {"logs": get_container_logs(container_id, tail)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/containers/{container_id}")
async def container_details(
    container_id: str,
    _: User = Depends(RequireViewer),
):
    try:
        return get_container_details(container_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
