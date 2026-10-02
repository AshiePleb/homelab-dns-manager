from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio

from app.database import get_db
from app.models import User, ProxyHost, LogLevel
from app.schemas import (
    CaddyStatusResponse,
    CaddyHostResponse,
    CertRenewRequest,
    CertRenewResponse,
    CertRenewExpiringRequest,
    CertRenewExpiringResponse,
)
from app.core.deps import RequireViewer, RequireOperator
from app.services.caddy_service import (
    get_container_status,
    read_caddyfile,
    get_ssl_status,
    reload_caddy,
    write_all_sites,
    prepare_cert_renewal,
    prepare_expiring_cert_renewals,
)
from app.services.settings_service import log_activity
from app.services.notification_service import send_notifications
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
    hosts = list(result.scalars().all())
    if not hosts:
        return []

    ssl_rows = await asyncio.gather(
        *(get_ssl_status(h.hostname, True, h.ssl_mode) for h in hosts)
    )
    return [
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
        for h, ssl in zip(hosts, ssl_rows)
    ]


@router.get("/config")
async def get_caddy_config(
    _: User = Depends(RequireViewer),
):
    content = read_caddyfile()
    return {"content": content or "", "path": "/data/caddy/Caddyfile"}


@router.post("/reload")
async def reload_caddy_proxy(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireOperator),
):
    # Write config now; restart after response so the UI connection survives.
    result = await db.execute(select(ProxyHost).where(ProxyHost.enabled == True))
    hosts = result.scalars().all()
    write_all_sites(
        [
            {
                "hostname": h.hostname,
                "forward_host": h.forward_host,
                "forward_port": h.forward_port,
                "ssl_mode": h.ssl_mode,
                "enabled": h.enabled,
            }
            for h in hosts
        ]
    )
    background_tasks.add_task(reload_caddy)
    return {"reloaded": True, "site_count": len(hosts), "reload_pending": True}


@router.post("/certs/renew", response_model=CertRenewResponse)
async def renew_certificate(
    data: CertRenewRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireOperator),
):
    """Force re-issue: delete on-disk cert, then restart Caddy after the response."""
    try:
        result = prepare_cert_renewal(data.hostname)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    background_tasks.add_task(reload_caddy)
    await log_activity(
        db,
        "ssl",
        f"Certificate renew requested for {result['hostname']}",
        LogLevel.INFO,
        details=result,
        user_id=user.id,
    )
    await send_notifications(
        db, "ssl_renewed", {"hostname": result["hostname"], "count": 1},
    )
    return CertRenewResponse(**result)


@router.post("/certs/renew-expiring", response_model=CertRenewExpiringResponse)
async def renew_expiring_certificates(
    data: CertRenewExpiringRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireOperator),
):
    """Force re-issue for certificates within the expiry window."""
    try:
        result = prepare_expiring_cert_renewals(data.within_days)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if result["reload_pending"]:
        background_tasks.add_task(reload_caddy)
    await log_activity(
        db,
        "ssl",
        result["message"],
        LogLevel.INFO,
        details={"within_days": data.within_days, "renewed_count": result["renewed_count"]},
        user_id=user.id,
    )
    if result.get("renewed_count"):
        await send_notifications(
            db,
            "ssl_renewed",
            {"count": result["renewed_count"], "hostname": None},
        )
    return CertRenewExpiringResponse(**result)
