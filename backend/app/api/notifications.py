from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.schemas import NotificationTestRequest, DiscordEmbedPreviewRequest
from app.core.deps import RequireAdmin
from app.services.notification_service import (
    send_test_notification,
    preview_embed,
    EVENT_DEFAULTS,
    SAMPLE_DATA,
    DEFAULT_ACCENT,
)
from app.services.settings_service import get_settings_dict

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post("/test")
async def test_notifications(
    data: NotificationTestRequest = NotificationTestRequest(),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireAdmin),
):
    event = data.event or "service_created"
    results = await send_test_notification(db, event=event)
    return {"results": results, "event": event}


@router.get("/events")
async def list_notification_events(_: User = Depends(RequireAdmin)):
    return {
        "events": [
            {"id": eid, "default_enabled": default == "true"}
            for eid, default in EVENT_DEFAULTS.items()
        ]
    }


@router.post("/discord/preview")
async def discord_embed_preview(
    data: DiscordEmbedPreviewRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireAdmin),
):
    cfg = await get_settings_dict(db, "notify.")
    accent = data.accent_color or cfg.get("discord_accent_color") or DEFAULT_ACCENT
    username = cfg.get("discord_username") or "HomeLab DNS"
    event = data.event if data.event in EVENT_DEFAULTS else "service_created"
    embed = preview_embed(event, accent=accent)
    return {
        "event": event,
        "username": username,
        "accent_color": accent,
        "sample_data": SAMPLE_DATA.get(event, {}),
        "embed": embed,
    }
