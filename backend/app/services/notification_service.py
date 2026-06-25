import httpx
import aiosmtplib
from email.mime.text import MIMEText
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.settings_service import get_settings_dict


async def send_discord_webhook(webhook_url: str, content: str, embed: dict | None = None):
    payload = {"content": content}
    if embed:
        payload["embeds"] = [embed]
    async with httpx.AsyncClient(timeout=15) as client:
        await client.post(webhook_url, json=payload)


async def send_email(
    host: str,
    port: int,
    username: str,
    password: str,
    from_addr: str,
    to_addr: str,
    subject: str,
    body: str,
):
    msg = MIMEText(body)
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    await aiosmtplib.send(
        msg,
        hostname=host,
        port=port,
        username=username,
        password=password,
        start_tls=True,
    )


async def send_notifications(db: AsyncSession, event: str, data: dict):
    cfg = await get_settings_dict(db, "notify.")
    if not cfg:
        return

    messages = {
        "ip_change": (
            f"🌐 Public IP changed: {data.get('old_ip', 'unknown')} → {data.get('new_ip')}"
            + (f" ({len(data.get('affected', []))} record(s) updated)" if data.get("affected") else ""),
            cfg.get("notify_ip_change", "true") == "true",
        ),
        "cf_failure": (
            f"❌ Cloudflare update failed: {data.get('message', 'Unknown error')}",
            cfg.get("notify_cf_failure", "true") == "true",
        ),
        "service_created": (
            f"✅ New service: {data.get('hostname', 'unknown')} → {data.get('target', 'unknown')}",
            cfg.get("notify_service_created", "true") == "true",
        ),
        "service_deleted": (
            f"🗑️ Service removed: {data.get('hostname', 'unknown')}",
            cfg.get("notify_service_deleted", "false") == "true",
        ),
        "record_created": (
            f"📝 New DNS record: {data.get('hostname', 'unknown')} ({data.get('record_type', '?')}) → {data.get('content', '')}",
            cfg.get("notify_record_created", "true") == "true",
        ),
        "record_deleted": (
            f"🗑️ DNS record removed: {data.get('hostname', 'unknown')}",
            cfg.get("notify_record_deleted", "false") == "true",
        ),
        "ssl_expiry": (
            f"🔒 SSL certificate expiring soon: {data.get('domain', 'unknown')}"
            + (f" ({data.get('days')} days left, expires {data.get('expires_at')})" if data.get("days") is not None else ""),
            cfg.get("notify_ssl_expiry", "true") == "true",
        ),
    }

    msg_info = messages.get(event)
    if not msg_info or not msg_info[1]:
        return

    message = msg_info[0]
    webhook = cfg.get("discord_webhook")
    if webhook:
        try:
            await send_discord_webhook(webhook, message)
        except Exception:
            pass

    smtp_host = cfg.get("smtp_host")
    if smtp_host and cfg.get("smtp_to"):
        try:
            await send_email(
                smtp_host,
                int(cfg.get("smtp_port", "587")),
                cfg.get("smtp_username", ""),
                cfg.get("smtp_password", ""),
                cfg.get("smtp_from", ""),
                cfg["smtp_to"],
                f"HomeLab DNS Manager: {event}",
                message,
            )
        except Exception:
            pass
