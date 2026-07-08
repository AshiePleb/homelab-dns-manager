"""External API for integrations (e.g. HomeLab WebHost Manager)."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import ApiKey, DNSRecord, ProxyHost, Domain
from app.schemas import (
    ExternalApiInfo,
    ServiceProvisionRequest,
    ServiceProvisionResponse,
    ServiceTemplateResponse,
    ServiceListItem,
    PortCheckResult,
)
from app.core.deps import get_api_key
from app.services.api_key_service import get_usage
from app.services.service_provision import (
    provision_service,
    list_provisioned_services,
    delete_service,
    get_default_zone,
    parse_host_port,
    build_fqdn,
)
from app.services.port_check import check_port
from app.services.cloudflare_service import get_cloudflare_service

router = APIRouter(prefix="/v1", tags=["external-api"])


def _api_base(request: Request) -> str:
    return f"{request.url.scheme}://{request.url.netloc}/api/v1"


@router.get("/info", response_model=ExternalApiInfo)
async def api_info(
    request: Request,
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(get_api_key),
):
    base = _api_base(request)
    usage = await get_usage(db, api_key)
    return ExternalApiInfo(
        key_name=api_key.name,
        api_base=base,
        limits={"max_dns_records": api_key.max_dns_records, "max_services": api_key.max_services},
        usage=usage,
        endpoints={
            "info": f"{base}/info",
            "template": f"{base}/services/template",
            "provision": f"{base}/services/provision",
            "services": f"{base}/services",
            "delete_service": f"{base}/services/{{proxy_host_id}}",
            "records": f"{base}/records",
            "delete_record": f"{base}/records/{{record_id}}",
            "check_port": f"{base}/services/check-port",
            "preview": f"{base}/services/preview",
        },
    )


@router.get("/services/template", response_model=ServiceTemplateResponse)
async def get_service_template(
    db: AsyncSession = Depends(get_db),
    _: ApiKey = Depends(get_api_key),
):
    base = await get_default_zone(db)
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


@router.get("/services", response_model=list[ServiceListItem])
async def list_services(
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(get_api_key),
):
    all_services = await list_provisioned_services(db)
    owned = await db.execute(
        select(ProxyHost.hostname).where(ProxyHost.api_key_id == api_key.id)
    )
    hostnames = {h for h in owned.scalars().all()}
    return [s for s in all_services if s["hostname"] in hostnames]


@router.get("/services/check-port", response_model=PortCheckResult)
async def check_target_port(
    host: str,
    port: int,
    _: ApiKey = Depends(get_api_key),
):
    result = await check_port(host, port)
    return PortCheckResult(**result)


@router.get("/services/preview")
async def preview_hostname(
    subdomain: str,
    base_domain: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: ApiKey = Depends(get_api_key),
):
    zone = base_domain or await get_default_zone(db)
    if not zone:
        raise HTTPException(status_code=400, detail="No default domain configured")
    hostname = build_fqdn(subdomain, zone)
    return {"hostname": hostname, "base_domain": zone, "subdomain": subdomain}


@router.post("/services/provision", response_model=ServiceProvisionResponse)
async def create_service(
    data: ServiceProvisionRequest,
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(get_api_key),
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
            api_key_id=api_key.id,
        )
        return ServiceProvisionResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/services/{service_id}")
async def remove_service(
    service_id: int,
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(get_api_key),
):
    result = await db.execute(select(ProxyHost).where(ProxyHost.id == service_id))
    host = result.scalar_one_or_none()
    if not host:
        raise HTTPException(status_code=404, detail="Service not found")
    if host.api_key_id != api_key.id:
        raise HTTPException(status_code=403, detail="This service was not created by your API key")
    try:
        await delete_service(db, service_id, api_key_id=api_key.id)
        return {"message": "Service removed"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/records")
async def list_records(
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(get_api_key),
):
    result = await db.execute(
        select(DNSRecord).where(DNSRecord.api_key_id == api_key.id).order_by(DNSRecord.id)
    )
    records = result.scalars().all()
    return [
        {
            "id": r.id,
            "hostname": r.hostname,
            "record_type": r.record_type,
            "content": r.content,
            "managed": r.managed,
            "proxied": r.proxied,
            "status": r.status,
        }
        for r in records
    ]


@router.delete("/records/{record_id}")
async def remove_record(
    record_id: int,
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(get_api_key),
):
    result = await db.execute(
        select(DNSRecord)
        .options(selectinload(DNSRecord.domain))
        .where(DNSRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    if record.api_key_id != api_key.id:
        raise HTTPException(status_code=403, detail="This record was not created by your API key")

    cf = await get_cloudflare_service(db)
    if cf and record.cloudflare_record_id and record.domain:
        try:
            await cf.delete_record(record.domain.zone_id, record.cloudflare_record_id)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to delete Cloudflare record: {e}")

    hostname = record.hostname
    await db.delete(record)
    await db.flush()

    proxy = await db.execute(select(ProxyHost).where(ProxyHost.hostname == hostname))
    proxy_host = proxy.scalar_one_or_none()
    if proxy_host and proxy_host.api_key_id == api_key.id:
        await delete_service(db, proxy_host.id, api_key_id=api_key.id)

    return {"message": "Record removed"}
