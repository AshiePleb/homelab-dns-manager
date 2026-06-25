from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, ProxyHost
from app.schemas import CaddyStatusResponse, CaddyHostResponse
from app.core.deps import RequireViewer, RequireOperator
from app.services.caddy_service import (
    get_container_status,
    read_caddyfile,
    get_ssl_status,
    sync_and_reload,
)
from app.config import get_settings

router = APIRouter(prefix="/caddy", tags=["caddy"])
settings = get_settings()


@router.get("/status", response_model=CaddyStatusResponse)
async def caddy_status(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireViewer),
):
    container = get_container_status()
    caddyfile = read_caddyfile()
    total = await db.scalar(select(func.count()).select_from(ProxyHost)) or 0
    enabled = await db.scalar(
        select(func.count()).select_from(ProxyHost).where(ProxyHost.enabled == True)
    ) or 0

    return CaddyStatusResponse(
        container_name=container["container"],
        container_running=container["running"],
        container_status=container["status"],
        container_message=container.get("message"),
        caddyfile_present=bool(caddyfile),
        site_count=enabled,
        total_hosts=total,
        acme_email=settings.acme_email,
    )


@router.get("/hosts", response_model=list[CaddyHostResponse])
async def list_caddy_hosts(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireViewer),
):
    result = await db.execute(select(ProxyHost).order_by(ProxyHost.hostname))
    hosts = result.scalars().all()
    responses = []
    for h in hosts:
        ssl = await get_ssl_status(h.hostname, True, h.ssl_mode)
        responses.append(
            CaddyHostResponse(
                id=h.id,
                hostname=h.hostname,
                forward_host=h.forward_host,
                forward_port=h.forward_port,
                ssl_mode=h.ssl_mode,
                enabled=h.enabled,
                port_reachable=h.port_reachable,
                mapping=f"{h.hostname} → {h.forward_host}:{h.forward_port}",
                ssl_status=ssl["ssl_status"],
                ssl_label=ssl["ssl_label"],
                ssl_message=ssl["ssl_message"],
                has_cert=ssl["ssl_status"] in ("active", "warning"),
                updated_at=h.updated_at,
            )
        )
    return responses


@router.get("/config")
async def get_caddy_config(
    _: User = Depends(RequireViewer),
):
    content = read_caddyfile()
    return {"content": content or "", "path": "/data/caddy/Caddyfile"}


@router.post("/reload")
async def reload_caddy_proxy(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireOperator),
):
    result = await sync_and_reload(db)
    return result
