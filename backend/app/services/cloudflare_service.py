import httpx
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Domain, DNSRecord, DNSRecordHistory, IPChangeLog, LogLevel
from app.services.settings_service import get_setting, log_activity
from app.config import get_settings

settings = get_settings()


class CloudflareService:
    BASE_URL = "https://api.cloudflare.com/client/v4"

    def __init__(self, api_token: str):
        self.api_token = api_token
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.request(
                method, f"{self.BASE_URL}{path}", headers=self.headers, **kwargs
            )
            data = resp.json()
            if not data.get("success", False):
                errors = data.get("errors", [{"message": "Unknown error"}])
                raise Exception(errors[0].get("message", "Cloudflare API error"))
            return data

    async def verify_token(self) -> dict:
        return await self._request("GET", "/user/tokens/verify")

    async def list_zones(self) -> list[dict]:
        data = await self._request("GET", "/zones")
        return data.get("result", [])

    async def list_records(self, zone_id: str) -> list[dict]:
        data = await self._request("GET", f"/zones/{zone_id}/dns_records")
        return data.get("result", [])

    async def create_record(self, zone_id: str, record: dict) -> dict:
        data = await self._request("POST", f"/zones/{zone_id}/dns_records", json=record)
        return data["result"]

    async def update_record(self, zone_id: str, record_id: str, record: dict) -> dict:
        data = await self._request(
            "PUT", f"/zones/{zone_id}/dns_records/{record_id}", json=record
        )
        return data["result"]

    async def delete_record(self, zone_id: str, record_id: str) -> None:
        await self._request("DELETE", f"/zones/{zone_id}/dns_records/{record_id}")

    async def toggle_proxy(self, zone_id: str, record_id: str, proxied: bool) -> dict:
        data = await self._request(
            "PATCH",
            f"/zones/{zone_id}/dns_records/{record_id}",
            json={"proxied": proxied},
        )
        return data["result"]


async def get_cloudflare_service(db: AsyncSession) -> CloudflareService | None:
    token = await get_setting(db, "cloudflare.api_token")
    if not token:
        return None
    return CloudflareService(token)


async def sync_zones(db: AsyncSession) -> list[Domain]:
    cf = await get_cloudflare_service(db)
    if not cf:
        raise Exception("Cloudflare not configured")
    zones = await cf.list_zones()
    synced = []
    for zone in zones:
        result = await db.execute(select(Domain).where(Domain.zone_id == zone["id"]))
        domain = result.scalar_one_or_none()
        if domain:
            domain.name = zone["name"]
            domain.status = zone["status"]
            domain.account_id = zone.get("account", {}).get("id")
        else:
            domain = Domain(
                zone_id=zone["id"],
                name=zone["name"],
                status=zone["status"],
                account_id=zone.get("account", {}).get("id"),
            )
            db.add(domain)
        synced.append(domain)
    await db.flush()
    await log_activity(db, "cloudflare", f"Synced {len(synced)} zones", LogLevel.SUCCESS)
    return synced


async def sync_records_for_domain(db: AsyncSession, domain_id: int) -> int:
    cf = await get_cloudflare_service(db)
    if not cf:
        raise Exception("Cloudflare not configured")
    result = await db.execute(select(Domain).where(Domain.id == domain_id))
    domain = result.scalar_one_or_none()
    if not domain:
        raise Exception("Domain not found")
    records = await cf.list_records(domain.zone_id)
    count = 0
    for rec in records:
        result = await db.execute(
            select(DNSRecord).where(
                DNSRecord.cloudflare_record_id == rec["id"]
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.hostname = rec["name"]
            existing.record_type = rec["type"]
            existing.content = rec["content"]
            existing.proxied = rec.get("proxied", False)
            existing.ttl = rec.get("ttl", 1)
            if not existing.app_created:
                existing.managed = False
        else:
            db.add(
                DNSRecord(
                    domain_id=domain.id,
                    cloudflare_record_id=rec["id"],
                    hostname=rec["name"],
                    record_type=rec["type"],
                    content=rec["content"],
                    proxied=rec.get("proxied", False),
                    ttl=rec.get("ttl", 1),
                    managed=False,
                    app_created=False,
                )
            )
        count += 1
    from datetime import datetime, timezone
    domain.last_synced_at = datetime.now(timezone.utc)
    await db.flush()
    return count


async def update_cloudflare_record(
    db: AsyncSession, record: DNSRecord, new_content: str, reason: str = "manual"
) -> None:
    cf = await get_cloudflare_service(db)
    if not cf:
        raise Exception("Cloudflare not configured")
    result = await db.execute(select(Domain).where(Domain.id == record.domain_id))
    domain = result.scalar_one_or_none()
    if not domain or not record.cloudflare_record_id:
        raise Exception("Record not linked to Cloudflare")
    old_content = record.content
    await cf.update_record(
        domain.zone_id,
        record.cloudflare_record_id,
        {
            "type": record.record_type,
            "name": record.hostname,
            "content": new_content,
            "ttl": record.ttl,
            "proxied": record.proxied,
        },
    )
    record.content = new_content
    from datetime import datetime, timezone
    record.last_updated_at = datetime.now(timezone.utc)
    db.add(
        DNSRecordHistory(
            record_id=record.id,
            old_content=old_content,
            new_content=new_content,
            change_reason=reason,
        )
    )
    await db.flush()
