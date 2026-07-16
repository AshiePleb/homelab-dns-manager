from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.schemas import (
    ServiceProvisionRequest,
    ServiceProvisionResponse,
    ServiceTemplateResponse,
    ServiceListItem,
    ServiceTargetUpdate,
    ServiceTargetUpdateResponse,
    PortCheckResult,
)
from app.core.deps import RequireViewer, RequireOperator
from app.services.service_provision import (
    provision_service,
    list_provisioned_services,
    delete_service,
    update_service_target,
    get_default_zone,
    parse_host_port,
    build_fqdn,
)
from app.services.port_check import check_port
from app.services.cloudflare_service import sync_zones
from sqlalchemy import select
from app.models import Domain

router = APIRouter(prefix="/services", tags=["services"])


@router.get("/template", response_model=ServiceTemplateResponse)
async def get_service_template(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireViewer),
):
    base = await get_default_zone(db)
    zones: list[str] = []
    result = await db.execute(select(Domain).order_by(Domain.name))
    zones = [d.name for d in result.scalars().all()]

    if not base and zones:
        base = zones[0]

    return ServiceTemplateResponse(
        base_domain=base,
        available_zones=zones,
        example_subdomain="home",
        example_hostname=f"home.{base}" if base else "home.example.com",
        example_target="10.10.10.1:8080",
    )


@router.get("", response_model=list[ServiceListItem])
async def list_services(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireViewer),
):
    return await list_provisioned_services(db)


@router.get("/check-port", response_model=PortCheckResult)
async def check_target_port(
    host: str,
    port: int,
    _: User = Depends(RequireViewer),
):
    result = await check_port(host, port)
    return PortCheckResult(**result)


@router.post("/provision", response_model=ServiceProvisionResponse)
async def create_service(
    data: ServiceProvisionRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireOperator),
):
    try:
        host = data.forward_host
        port = data.forward_port
        if data.target:
            host, port = parse_host_port(data.target, data.forward_port)

        if data.ssl_mode not in ("letsencrypt",):
            data.ssl_mode = "letsencrypt"

        result = await provision_service(
            db,
            subdomain=data.subdomain,
            forward_host=host,
            forward_port=port,
            base_domain=data.base_domain,
            ssl_mode=data.ssl_mode,
            create_dns=data.create_dns,
            create_proxy=data.create_proxy,
            skip_port_check=data.skip_port_check,
            user_id=user.id,
        )
        return ServiceProvisionResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{service_id}", response_model=ServiceTargetUpdateResponse)
async def update_service(
    service_id: int,
    data: ServiceTargetUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireOperator),
):
    try:
        host = data.forward_host
        port = data.forward_port or 80
        if data.target:
            host, port = parse_host_port(data.target, port)
        if not host:
            raise ValueError("Target host is required")
        result = await update_service_target(
            db,
            service_id,
            forward_host=host,
            forward_port=port,
            skip_port_check=data.skip_port_check,
            user_id=user.id,
        )
        return ServiceTargetUpdateResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{service_id}")
async def remove_service(
    service_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireOperator),
):
    try:
        await delete_service(db, service_id, user_id=user.id)
        return {"message": "Service removed"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/preview")
async def preview_hostname(
    subdomain: str,
    base_domain: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireViewer),
):
    zone = base_domain or await get_default_zone(db)
    if not zone:
        raise HTTPException(status_code=400, detail="No default domain configured")
    hostname = build_fqdn(subdomain, zone)
    return {"hostname": hostname, "base_domain": zone, "subdomain": subdomain}
