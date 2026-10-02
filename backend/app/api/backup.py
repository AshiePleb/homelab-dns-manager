from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import RequireAdmin
from app.database import get_db
from app.models import User, LogLevel
from app.services.backup_service import create_backup_zip, restore_backup_zip
from app.services.settings_service import log_activity
from app.services.notification_service import send_notifications

router = APIRouter(prefix="/backup", tags=["backup"])


@router.get("/export")
async def export_backup(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireAdmin),
):
    data = create_backup_zip()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    await log_activity(
        db, "backup", "Backup exported", LogLevel.INFO,
        details={"bytes": len(data)}, user_id=user.id,
    )
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="homelab-dns-backup-{stamp}.zip"'},
    )


@router.post("/restore")
async def import_backup(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireAdmin),
):
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Upload a .zip backup file")
    data = await file.read()
    if len(data) < 100:
        raise HTTPException(status_code=400, detail="Backup file is too small")
    try:
        restore_backup_zip(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Restore failed: {e}") from e
    await log_activity(
        db, "backup", "Backup restored", LogLevel.WARNING,
        details={"filename": file.filename}, user_id=user.id,
    )
    await send_notifications(
        db, "backup_restored",
        {"message": f"Restored from {file.filename}"},
    )
    return {"message": "Backup restored. Restart the container to apply all changes."}
