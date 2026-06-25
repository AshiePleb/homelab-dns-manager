import httpx
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import NPMProxyHost, LogLevel
from app.services.settings_service import get_settings_dict, log_activity


class NPMService:
    def __init__(self, base_url: str, email: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self.token: str | None = None

    async def _login(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            f"{self.base_url}/api/tokens",
            json={"identity": self.email, "secret": self.password},
        )
        resp.raise_for_status()
        data = resp.json()
        self.token = data.get("token")

    async def _get_client(self) -> httpx.AsyncClient:
        client = httpx.AsyncClient(timeout=30)
        await self._login(client)
        client.headers["Authorization"] = f"Bearer {self.token}"
        return client

    async def list_proxy_hosts(self) -> list[dict]:
        async with await self._get_client() as client:
            resp = await client.get(f"{self.base_url}/api/nginx/proxy-hosts")
            resp.raise_for_status()
            return resp.json()

    async def create_proxy_host(self, host_data: dict) -> dict:
        async with await self._get_client() as client:
            resp = await client.post(
                f"{self.base_url}/api/nginx/proxy-hosts", json=host_data
            )
            resp.raise_for_status()
            return resp.json()

    async def delete_proxy_host(self, host_id: int) -> None:
        async with await self._get_client() as client:
            resp = await client.delete(
                f"{self.base_url}/api/nginx/proxy-hosts/{host_id}"
            )
            resp.raise_for_status()

    async def get_certificates(self) -> list[dict]:
        async with await self._get_client() as client:
            resp = await client.get(f"{self.base_url}/api/nginx/certificates")
            resp.raise_for_status()
            return resp.json()


async def get_npm_service(db: AsyncSession) -> NPMService | None:
    cfg = await get_settings_dict(db, "npm.")
    if not cfg.get("url") or not cfg.get("username") or not cfg.get("password"):
        return None
    return NPMService(cfg["url"], cfg["username"], cfg["password"])


async def sync_npm_hosts(db: AsyncSession) -> list[NPMProxyHost]:
    npm = await get_npm_service(db)
    if not npm:
        raise Exception("NPM not configured")
    hosts = await npm.list_proxy_hosts()
    synced = []
    for host in hosts:
        result = await db.execute(
            select(NPMProxyHost).where(NPMProxyHost.npm_id == host["id"])
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.domain_names = host.get("domain_names", [])
            existing.forward_host = host.get("forward_host", "")
            existing.forward_port = host.get("forward_port", 80)
            existing.ssl_enabled = bool(host.get("certificate_id"))
            existing.certificate_id = host.get("certificate_id")
            existing.last_synced_at = datetime.now(timezone.utc)
        else:
            existing = NPMProxyHost(
                npm_id=host["id"],
                domain_names=host.get("domain_names", []),
                forward_host=host.get("forward_host", ""),
                forward_port=host.get("forward_port", 80),
                ssl_enabled=bool(host.get("certificate_id")),
                certificate_id=host.get("certificate_id"),
                last_synced_at=datetime.now(timezone.utc),
            )
            db.add(existing)
        synced.append(existing)
    await db.flush()
    await log_activity(
        db, "npm", f"Synced {len(synced)} proxy hosts", LogLevel.SUCCESS
    )
    return synced
