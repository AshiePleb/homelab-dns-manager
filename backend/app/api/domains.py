from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import User, Domain, DNSRecord, DNSRecordHistory, ProxyHost, ActivityLog, LogLevel, IPChangeLog
from app.schemas import (
    DomainResponse,
    DNSRecordCreate,
    DNSRecordUpdate,
    DNSRecordResponse,
    DNSRecordHistoryResponse,
    DashboardStats,
    ActivityLogResponse,
    DDNSStatus,
    IPChangeLogResponse,
    ManagedDDNSHost,
    ServiceHealthRow,
    BulkRecordsRequest,
    BulkRecordsResponse,
    HealthHistoryPoint,
)
from app.core.deps import RequireViewer, RequireOperator
from app.services.cloudflare_service import (
    sync_zones,
    sync_records_for_domain,
    get_cloudflare_service,
    update_cloudflare_record,
)
from app.services.ddns_service import get_ddns_status, run_ddns_check, get_managed_hostnames
from app.services.health_service import get_services_health
from app.services.health_history_service import get_health_history
from app.services.settings_service import get_setting, log_activity
from sqlalchemy import desc

router_domains = APIRouter(prefix="/domains", tags=["domains"])
router_records = APIRouter(prefix="/records", tags=["records"])
router_ddns = APIRouter(prefix="/ddns", tags=["ddns"])
router_dashboard = APIRouter(prefix="/dashboard", tags=["dashboard"])
router_logs = APIRouter(prefix="/logs", tags=["logs"])
router_cf = APIRouter(prefix="/cloudflare", tags=["cloudflare"])


@router_dashboard.get("/stats", response_model=DashboardStats)
async def dashboard_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireViewer),
):
    ddns = await get_ddns_status(db)
    cf = await get_cloudflare_service(db)
    records_count = await db.scalar(
        select(func.count()).select_from(DNSRecord).where(
            DNSRecord.managed == True, DNSRecord.app_created == True
        )
    )
    proxy_count = await db.scalar(select(func.count()).select_from(ProxyHost))
    unhealthy = await db.scalar(
        select(func.count()).select_from(ProxyHost).where(
            ProxyHost.enabled == True,
            ProxyHost.port_reachable == False,
        )
    )
    return DashboardStats(
        current_public_ip=ddns["current_ip"],
        last_ip_change=ddns["last_change"],
        cloudflare_status="connected" if cf else "not_configured",
        dns_records_managed=records_count or 0,
        proxy_hosts=proxy_count or 0,
        system_health="degraded" if unhealthy else "healthy",
    )


@router_dashboard.get("/health", response_model=list[ServiceHealthRow])
async def dashboard_health(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireViewer),
):
    return await get_services_health(db)


@router_dashboard.get("/health/history", response_model=list[HealthHistoryPoint])
async def dashboard_health_history(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireViewer),
    hostname: str | None = None,
    hours: int = 24,
):
    return await get_health_history(db, hostname=hostname, hours=hours)


@router_dashboard.get("/activity", response_model=list[ActivityLogResponse])
async def recent_activity(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireViewer),
    limit: int = 10,
):
    result = await db.execute(
        select(ActivityLog).order_by(desc(ActivityLog.created_at)).limit(limit)
    )
    return result.scalars().all()


@router_domains.get("", response_model=list[DomainResponse])
async def list_domains(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireViewer),
):
    result = await db.execute(select(Domain).order_by(Domain.name))
    domains = result.scalars().all()
    responses = []
    for d in domains:
        count = await db.scalar(
            select(func.count()).select_from(DNSRecord).where(
                DNSRecord.domain_id == d.id, DNSRecord.app_created == True
            )
        )
        responses.append(
            DomainResponse(
                id=d.id,
                zone_id=d.zone_id,
                name=d.name,
                status=d.status,
                record_count=count or 0,
                last_synced_at=d.last_synced_at,
                created_at=d.created_at,
            )
        )
    return responses


@router_domains.post("/sync")
async def sync_all_domains(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireOperator),
):
    from app.services.service_provision import get_default_zone, set_default_zone

    domains = await sync_zones(db)
    if domains and not await get_default_zone(db):
        apex = min(domains, key=lambda d: len(d.name))
        await set_default_zone(db, apex.name)
    return {"synced": len(domains)}


@router_domains.post("/{domain_id}/sync")
async def sync_domain(
    domain_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireOperator),
):
    count = await sync_records_for_domain(db, domain_id)
    return {"synced_records": count}


@router_domains.delete("/{domain_id}")
async def delete_domain(
    domain_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireOperator),
):
    result = await db.execute(select(Domain).where(Domain.id == domain_id))
    domain = result.scalar_one_or_none()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    await db.delete(domain)
    return {"message": "Domain deleted"}


@router_records.get("", response_model=list[DNSRecordResponse])
async def list_records(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireViewer),
    domain_id: int | None = None,
    app_only: bool = True,
):
    query = select(DNSRecord).options(selectinload(DNSRecord.domain))
    if app_only:
        query = query.where(DNSRecord.app_created == True)
    if domain_id:
        query = query.where(DNSRecord.domain_id == domain_id)
    result = await db.execute(query.order_by(DNSRecord.hostname))
    records = result.scalars().all()

    proxy_result = await db.execute(select(ProxyHost))
    proxies_by_host = {p.hostname: p for p in proxy_result.scalars().all()}

    from app.services.caddy_service import get_ssl_status

    responses = []
    for r in records:
        proxy = proxies_by_host.get(r.hostname)
        ssl = await get_ssl_status(
            r.hostname,
            has_proxy=proxy is not None,
            ssl_mode=proxy.ssl_mode if proxy else None,
        )
        responses.append(
            DNSRecordResponse(
                id=r.id,
                domain_id=r.domain_id,
                domain_name=r.domain.name if r.domain else None,
                cloudflare_record_id=r.cloudflare_record_id,
                hostname=r.hostname,
                record_type=r.record_type,
                content=r.content,
                proxied=r.proxied,
                managed=r.managed,
                ttl=r.ttl,
                status=r.status,
                last_updated_at=r.last_updated_at,
                created_at=r.created_at,
                proxy_id=proxy.id if proxy else None,
                forward_host=proxy.forward_host if proxy else None,
                forward_port=proxy.forward_port if proxy else None,
                port_reachable=proxy.port_reachable if proxy else None,
                ssl_provider=ssl["ssl_provider"],
                ssl_mode=ssl["ssl_mode"],
                ssl_status=ssl["ssl_status"],
                ssl_label=ssl["ssl_label"],
                ssl_message=ssl["ssl_message"],
            )
        )
    return responses


@router_records.post("", response_model=DNSRecordResponse, status_code=201)
async def create_record(
    data: DNSRecordCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireOperator),
):
    from app.services.bootstrap_service import ensure_managed_ddns_hostname
    from app.services.ddns_service import get_public_ip

    result = await db.execute(select(Domain).where(Domain.id == data.domain_id))
    domain = result.scalar_one_or_none()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    # Managed A records: create in Cloudflare + auto-register for DDNS (replaces favonia DOMAINS=)
    if data.managed and data.record_type == "A":
        try:
            current_ip = await get_public_ip()
        except Exception:
            current_ip = data.content or "0.0.0.0"
        record = await ensure_managed_ddns_hostname(
            db,
            data.hostname,
            proxied=data.proxied,
            current_ip=current_ip if not data.content or data.content == "0.0.0.0" else data.content,
        )
        if record:
            record.app_created = True
            if data.proxied != record.proxied:
                record.proxied = data.proxied
            await db.flush()
            await log_activity(
                db,
                "dns",
                f"Created DDNS-managed record {data.hostname}",
                LogLevel.SUCCESS,
                user_id=user.id,
            )
            from app.services.notification_service import send_notifications
            await send_notifications(
                db,
                "record_created",
                {
                    "hostname": record.hostname,
                    "record_type": record.record_type,
                    "content": record.content,
                },
            )
            return DNSRecordResponse(
                id=record.id,
                domain_id=record.domain_id,
                domain_name=domain.name,
                cloudflare_record_id=record.cloudflare_record_id,
                hostname=record.hostname,
                record_type=record.record_type,
                content=record.content,
                proxied=record.proxied,
                managed=record.managed,
                ttl=record.ttl,
                status=record.status,
                last_updated_at=record.last_updated_at,
                created_at=record.created_at,
            )

    cf = await get_cloudflare_service(db)
    cf_record_id = None
    if cf:
        try:
            cf_rec = await cf.create_record(
                domain.zone_id,
                {
                    "type": data.record_type,
                    "name": data.hostname,
                    "content": data.content,
                    "ttl": data.ttl,
                    "proxied": data.proxied,
                },
            )
            cf_record_id = cf_rec["id"]
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    record = DNSRecord(
        domain_id=data.domain_id,
        cloudflare_record_id=cf_record_id,
        hostname=data.hostname,
        record_type=data.record_type,
        content=data.content,
        proxied=data.proxied,
        managed=data.managed,
        app_created=True,
        ttl=data.ttl,
    )
    db.add(record)
    await db.flush()
    await log_activity(
        db, "dns", f"Created record {data.hostname}", LogLevel.SUCCESS, user_id=user.id
    )
    from app.services.notification_service import send_notifications
    await send_notifications(
        db,
        "record_created",
        {
            "hostname": record.hostname,
            "record_type": record.record_type,
            "content": record.content,
        },
    )
    return DNSRecordResponse(
        id=record.id,
        domain_id=record.domain_id,
        domain_name=domain.name,
        cloudflare_record_id=record.cloudflare_record_id,
        hostname=record.hostname,
        record_type=record.record_type,
        content=record.content,
        proxied=record.proxied,
        managed=record.managed,
        ttl=record.ttl,
        status=record.status,
        last_updated_at=record.last_updated_at,
        created_at=record.created_at,
    )


@router_records.post("/bulk", response_model=BulkRecordsResponse)
async def bulk_records(
    data: BulkRecordsRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireOperator),
):
    from app.services.ddns_service import get_public_ip

    action = data.action.lower()
    if action not in ("enable_ddns", "disable_ddns", "force_update", "delete"):
        raise HTTPException(status_code=400, detail="Invalid action")

    updated = 0
    errors: list[str] = []

    for record_id in data.record_ids:
        result = await db.execute(
            select(DNSRecord).options(selectinload(DNSRecord.domain)).where(DNSRecord.id == record_id)
        )
        record = result.scalar_one_or_none()
        if not record:
            errors.append(f"Record {record_id} not found")
            continue
        try:
            if action == "enable_ddns":
                record.managed = True
                if record.record_type == "A":
                    ip = await get_public_ip()
                    await update_cloudflare_record(db, record, ip, reason="bulk_enable_ddns")
                updated += 1
            elif action == "disable_ddns":
                record.managed = False
                updated += 1
            elif action == "force_update":
                if not record.managed:
                    errors.append(f"{record.hostname}: not DDNS managed")
                    continue
                ip = await get_public_ip()
                await update_cloudflare_record(db, record, ip, reason="bulk_force_update")
                updated += 1
            elif action == "delete":
                proxy_result = await db.execute(
                    select(ProxyHost).where(ProxyHost.hostname == record.hostname)
                )
                proxy = proxy_result.scalar_one_or_none()
                if proxy:
                    from app.services.service_provision import delete_service
                    await delete_service(db, proxy.id, user_id=user.id)
                else:
                    cf = await get_cloudflare_service(db)
                    if cf and record.cloudflare_record_id and record.domain:
                        await cf.delete_record(record.domain.zone_id, record.cloudflare_record_id)
                    await db.delete(record)
                updated += 1
            else:
                errors.append(f"{record.hostname}: unknown action")
        except Exception as e:
            errors.append(f"{record.hostname}: {e}")

    await log_activity(
        db,
        "dns",
        f"Bulk {action} on {updated} record(s)",
        LogLevel.INFO,
        user_id=user.id,
    )
    return BulkRecordsResponse(updated=updated, errors=errors)


@router_records.patch("/{record_id}", response_model=DNSRecordResponse)
async def update_record(
    record_id: int,
    data: DNSRecordUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireOperator),
):
    result = await db.execute(
        select(DNSRecord).options(selectinload(DNSRecord.domain)).where(DNSRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    if data.content and data.content != record.content:
        await update_cloudflare_record(db, record, data.content)
    if data.hostname is not None:
        record.hostname = data.hostname
    if data.record_type is not None:
        record.record_type = data.record_type
    if data.proxied is not None:
        record.proxied = data.proxied
    if data.managed is not None:
        record.managed = data.managed
        if data.managed and record.record_type == "A":
            from app.services.ddns_service import get_public_ip
            try:
                ip = await get_public_ip()
                await update_cloudflare_record(db, record, ip, reason="ddns_enabled")
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))
    if data.ttl is not None:
        record.ttl = data.ttl
    await db.flush()
    return DNSRecordResponse(
        id=record.id,
        domain_id=record.domain_id,
        domain_name=record.domain.name if record.domain else None,
        cloudflare_record_id=record.cloudflare_record_id,
        hostname=record.hostname,
        record_type=record.record_type,
        content=record.content,
        proxied=record.proxied,
        managed=record.managed,
        ttl=record.ttl,
        status=record.status,
        last_updated_at=record.last_updated_at,
        created_at=record.created_at,
    )


@router_records.delete("/{record_id}")
async def delete_record(
    record_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireOperator),
):
    result = await db.execute(
        select(DNSRecord).options(selectinload(DNSRecord.domain)).where(DNSRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    proxy_result = await db.execute(select(ProxyHost).where(ProxyHost.hostname == record.hostname))
    proxy = proxy_result.scalar_one_or_none()
    if proxy:
        from app.services.service_provision import delete_service
        await delete_service(db, proxy.id, user_id=user.id)

    cf = await get_cloudflare_service(db)
    if cf and record.cloudflare_record_id and record.domain:
        try:
            await cf.delete_record(record.domain.zone_id, record.cloudflare_record_id)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    await db.delete(record)
    await log_activity(db, "dns", f"Deleted record {record.hostname}", LogLevel.WARNING, user_id=user.id)
    from app.services.notification_service import send_notifications
    await send_notifications(db, "record_deleted", {"hostname": record.hostname})
    return {"message": "Record deleted"}


@router_records.post("/{record_id}/force-update")
async def force_update_record(
    record_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireOperator),
):
    from app.services.ddns_service import get_public_ip
    result = await db.execute(select(DNSRecord).where(DNSRecord.id == record_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    ip = await get_public_ip()
    await update_cloudflare_record(db, record, ip, reason="force_update")
    await log_activity(db, "dns", f"Force updated {record.hostname} to {ip}", LogLevel.SUCCESS, user_id=user.id)
    return {"ip": ip}


@router_records.get("/{record_id}/history", response_model=list[DNSRecordHistoryResponse])
async def record_history(
    record_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireViewer),
):
    result = await db.execute(
        select(DNSRecordHistory)
        .where(DNSRecordHistory.record_id == record_id)
        .order_by(desc(DNSRecordHistory.created_at))
    )
    return result.scalars().all()


@router_ddns.get("/managed", response_model=list[ManagedDDNSHost])
async def ddns_managed_hosts(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireViewer),
):
    return await get_managed_hostnames(db)


@router_ddns.get("/status", response_model=DDNSStatus)
async def ddns_status(db: AsyncSession = Depends(get_db), _: User = Depends(RequireViewer)):
    status = await get_ddns_status(db)
    return DDNSStatus(**status)


@router_ddns.post("/check")
async def ddns_check(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(RequireOperator),
):
    result = await run_ddns_check(db)
    return result or {"changed": False}


@router_ddns.get("/history", response_model=list[IPChangeLogResponse])
async def ip_history(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireViewer),
    limit: int = 50,
):
    result = await db.execute(
        select(IPChangeLog).order_by(desc(IPChangeLog.created_at)).limit(limit)
    )
    return result.scalars().all()


@router_logs.get("", response_model=list[ActivityLogResponse])
async def list_logs(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireViewer),
    level: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    query = select(ActivityLog).order_by(desc(ActivityLog.created_at))
    if level:
        query = query.where(ActivityLog.level == level)
    result = await db.execute(query.offset(offset).limit(limit))
    return result.scalars().all()


@router_cf.post("/test")
async def test_cloudflare(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireOperator),
):
    cf = await get_cloudflare_service(db)
    if not cf:
        raise HTTPException(status_code=400, detail="Cloudflare not configured")
    try:
        result = await cf.verify_token()
        return {"status": "ok", "result": result.get("result", {})}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router_cf.post("/sync")
async def cloudflare_sync(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequireOperator),
):
    domains = await sync_zones(db)
    total = 0
    for d in domains:
        total += await sync_records_for_domain(db, d.id)
    return {"zones": len(domains), "records": total}
