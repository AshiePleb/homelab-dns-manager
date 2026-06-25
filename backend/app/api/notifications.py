from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.core.deps import RequireAdmin
from app.services.notification_service import send_discord_webhook, send_email
from app.services.settings_service import get_settings_dict

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post("/test")
async def test_notifications(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireAdmin),
):
    cfg = await get_settings_dict(db, "notify.")
    results = []

    webhook = cfg.get("discord_webhook")
    if webhook:
        try:
            await send_discord_webhook(webhook, "✅ HomeLab DNS Manager test notification")
            results.append({"channel": "discord", "status": "ok"})
        except Exception as e:
            results.append({"channel": "discord", "status": "error", "message": str(e)})

    if cfg.get("smtp_host") and cfg.get("smtp_to"):
        try:
            await send_email(
                cfg["smtp_host"],
                int(cfg.get("smtp_port", "587")),
                cfg.get("smtp_username", ""),
                cfg.get("smtp_password", ""),
                cfg.get("smtp_from", ""),
                cfg["smtp_to"],
                "HomeLab DNS Manager Test",
                "This is a test notification from HomeLab DNS Manager.",
            )
            results.append({"channel": "email", "status": "ok"})
        except Exception as e:
            results.append({"channel": "email", "status": "error", "message": str(e)})

    return {"results": results}
