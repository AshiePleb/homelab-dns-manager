from fastapi import APIRouter, Depends

from app.core.deps import RequireViewer
from app.models import User
from app.schemas import VersionStatusResponse
from app.services.version_service import get_version_status

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/version", response_model=VersionStatusResponse)
async def version_status(_: User = Depends(RequireViewer)):
    return await get_version_status()
