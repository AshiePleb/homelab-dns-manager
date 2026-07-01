from contextlib import asynccontextmanager
import os
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models import User, UserRole, ProxyHost
from app.core.security import hash_password
from app.core.rate_limit import limiter
from app.core.websocket import ws_manager
from app.services.ddns_service import run_ddns_check
from app.services.bootstrap_service import run_startup_bootstrap
from app.services.cert_monitor import check_certificate_expiry
from app.services.settings_service import get_setting, set_setting
from app.services.caddy_service import write_all_sites, reload_caddy
from app.services.health_history_service import record_health_snapshots
from app.services.session_service import cleanup_expired_sessions, purge_old_sessions

from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.domains import (
    router_domains,
    router_records,
    router_ddns,
    router_dashboard,
    router_logs,
    router_cf,
)
from app.api.npm import router as npm_router
from app.api.docker import router as docker_router
from app.api.settings import router as settings_router
from app.api.notifications import router as notifications_router
from app.api.services import router as services_router
from app.api.preferences import router as preferences_router
from app.api.backup import router as backup_router

settings = get_settings()
scheduler = AsyncIOScheduler()


async def seed_admin():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.role == UserRole.ADMIN))
        if result.scalar_one_or_none():
            return
        admin = User(
            username=settings.admin_username,
            name=settings.admin_name,
            email=settings.admin_email,
            hashed_password=hash_password(settings.admin_password),
            role=UserRole.ADMIN,
            must_change_credentials=True,
        )
        db.add(admin)
        await set_setting(db, "general.theme", "midnight")
        await set_setting(db, "general.timezone", "UTC")
        await set_setting(db, "general.refresh_interval", str(settings.ddns_interval_minutes))
        await db.commit()


async def ddns_job():
    async with AsyncSessionLocal() as db:
        try:
            result = await run_ddns_check(db)
            await db.commit()
            if result and result.get("changed"):
                await ws_manager.broadcast("ip_changed", result)
        except Exception:
            await db.rollback()


async def sync_caddy_config():
    async with AsyncSessionLocal() as db:
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
        reload_caddy()


async def health_history_job():
    async with AsyncSessionLocal() as db:
        try:
            await record_health_snapshots(db)
            await db.commit()
        except Exception:
            await db.rollback()


async def session_cleanup_job():
    async with AsyncSessionLocal() as db:
        try:
            await cleanup_expired_sessions(db)
            await purge_old_sessions(db)
            await db.commit()
        except Exception:
            await db.rollback()


async def ssl_expiry_job():
    async with AsyncSessionLocal() as db:
        try:
            await check_certificate_expiry(db)
            await db.commit()
        except Exception:
            await db.rollback()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await seed_admin()
    async with AsyncSessionLocal() as db:
        try:
            await run_startup_bootstrap(db)
            await db.commit()
        except Exception:
            await db.rollback()
    try:
        await sync_caddy_config()
    except Exception:
        pass
    interval = int(await _get_interval())
    scheduler.add_job(ddns_job, "interval", minutes=interval, id="ddns_check")
    scheduler.add_job(session_cleanup_job, "interval", hours=1, id="session_cleanup")
    scheduler.add_job(health_history_job, "interval", minutes=15, id="health_history", next_run_time=datetime.now())
    scheduler.add_job(ssl_expiry_job, "interval", hours=12, id="ssl_expiry_check", next_run_time=datetime.now())
    scheduler.start()
    yield
    scheduler.shutdown()


async def _get_interval() -> str:
    async with AsyncSessionLocal() as db:
        return await get_setting(db, "general.refresh_interval") or str(settings.ddns_interval_minutes)


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api"
app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(users_router, prefix=API_PREFIX)
app.include_router(router_domains, prefix=API_PREFIX)
app.include_router(router_records, prefix=API_PREFIX)
app.include_router(router_ddns, prefix=API_PREFIX)
app.include_router(router_dashboard, prefix=API_PREFIX)
app.include_router(router_logs, prefix=API_PREFIX)
app.include_router(router_cf, prefix=API_PREFIX)
app.include_router(npm_router, prefix=API_PREFIX)
app.include_router(docker_router, prefix=API_PREFIX)
app.include_router(settings_router, prefix=API_PREFIX)
app.include_router(notifications_router, prefix=API_PREFIX)
app.include_router(services_router, prefix=API_PREFIX)
app.include_router(caddy_router, prefix=API_PREFIX)
app.include_router(preferences_router, prefix=API_PREFIX)
app.include_router(backup_router, prefix=API_PREFIX)


@app.get(f"{API_PREFIX}/health")
async def health():
    return {"status": "healthy"}


@app.websocket(f"{API_PREFIX}/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIR, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = os.path.join(FRONTEND_DIR, full_path)
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.debug)
