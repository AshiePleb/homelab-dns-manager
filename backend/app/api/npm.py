from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, NPMProxyHost, LogLevel
from app.schemas import NPMProxyHostCreate, NPMProxyHostResponse
from app.core.deps import RequireViewer, RequireOperator
from app.services.npm_service import get_npm_service, sync_npm_hosts
from app.services.settings_service import log_activity
from datetime import datetime, timezone

router = APIRouter(prefix="/npm", tags=["npm"])


def _host_response(h: NPMProxyHost) -> NPMProxyHostResponse:
    domains = h.domain_names or []
    mapping = None
    if domains:
        mapping = f"{domains[0]} -> {h.forward_host}:{h.forward_port}"
    return NPMProxyHostResponse(
        id=h.id,
        npm_id=h.npm_id,
        domain_names=domains,
        forward_host=h.forward_host,
        forward_port=h.forward_port,
        ssl_enabled=h.ssl_enabled,
        mapping=mapping,
        last_synced_at=h.last_synced_at,
    )


@router.get("/hosts", response_model=list[NPMProxyHostResponse])
async def list_hosts(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireViewer),
):
    result = await db.execute(select(NPMProxyHost).order_by(NPMProxyHost.id))
    return [_host_response(h) for h in result.scalars().all()]


@router.post("/sync")
async def sync_hosts(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireOperator),
):
    hosts = await sync_npm_hosts(db)
    return {"synced": len(hosts)}


@router.post("/hosts", response_model=NPMProxyHostResponse, status_code=201)
async def create_host(
    data: NPMProxyHostCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireOperator),
):
    npm = await get_npm_service(db)
    if not npm:
        raise HTTPException(status_code=400, detail="NPM not configured")

    host_data = {
        "domain_names": data.domain_names,
        "forward_scheme": "http",
        "forward_host": data.forward_host,
        "forward_port": data.forward_port,
        "access_list_id": 0,
        "certificate_id": 0,
        "ssl_forced": data.ssl_enabled,
        "caching_enabled": True,
        "block_exploits": True,
        "advanced_config": "",
        "meta": {"letsencrypt_agree": False, "dns_challenge": False},
        "allow_websocket_upgrade": True,
        "http2_support": True,
        "enabled": True,
        "locations": [],
    }

    try:
        created = await npm.create_proxy_host(host_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    host = NPMProxyHost(
        npm_id=created.get("id"),
        domain_names=data.domain_names,
        forward_host=data.forward_host,
        forward_port=data.forward_port,
        ssl_enabled=data.ssl_enabled,
        last_synced_at=datetime.now(timezone.utc),
    )
    db.add(host)

    if data.create_dns and data.domain_names:
        from app.services.bootstrap_service import ensure_managed_ddns_hostname
        from app.services.ddns_service import get_public_ip
        try:
            public_ip = await get_public_ip()
        except Exception:
            public_ip = None
        for domain_name in data.domain_names:
            if public_ip:
                try:
                    await ensure_managed_ddns_hostname(
                        db, domain_name, proxied=data.dns_proxied, current_ip=public_ip
                    )
                except Exception:
                    pass

    await db.flush()
    await log_activity(
        db,
        "npm",
        f"Created proxy host for {', '.join(data.domain_names)}",
        LogLevel.SUCCESS,
        user_id=user.id,
    )
    return _host_response(host)


@router.delete("/hosts/{host_id}")
async def delete_host(
    host_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireOperator),
):
    result = await db.execute(select(NPMProxyHost).where(NPMProxyHost.id == host_id))
    host = result.scalar_one_or_none()
    if not host:
        raise HTTPException(status_code=404, detail="Host not found")
    npm = await get_npm_service(db)
    if npm and host.npm_id:
        try:
            await npm.delete_proxy_host(host.npm_id)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    await db.delete(host)
    await log_activity(db, "npm", f"Deleted proxy host {host.domain_names}", LogLevel.WARNING, user_id=user.id)
    return {"message": "Host deleted"}


@router.get("/certificates")
async def list_certificates(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireViewer),
):
    npm = await get_npm_service(db)
    if not npm:
        raise HTTPException(status_code=400, detail="NPM not configured")
    try:
        return await npm.get_certificates()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
