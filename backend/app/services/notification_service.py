"""Discord webhook + SMTP notifications with plain text or rich embeds."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import aiosmtplib
import httpx
from email.mime.text import MIMEText
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.settings_service import get_settings_dict

DEFAULT_ACCENT = "#5865F2"
COLOR_SUCCESS = 0x57F287
COLOR_WARNING = 0xFEE75C
COLOR_ERROR = 0xED4245
COLOR_INFO = 0x5865F2

# Toggle key → default enabled string
EVENT_DEFAULTS: dict[str, str] = {
    "ip_change": "true",
    "cf_failure": "true",
    "service_created": "true",
    "service_deleted": "false",
    "service_updated": "true",
    "record_created": "true",
    "record_deleted": "false",
    "record_updated": "false",
    "ssl_expiry": "true",
    "ssl_renewed": "true",
    "app_update": "true",
    "zone_synced": "false",
    "domain_migrated": "false",
    "login_failed": "true",
    "user_changed": "false",
    "api_key_changed": "false",
    "settings_changed": "false",
    "backup_restored": "false",
}

SAMPLE_DATA: dict[str, dict[str, Any]] = {
    "ip_change": {"old_ip": "1.2.3.4", "new_ip": "5.6.7.8", "affected": ["home.example.com"]},
    "cf_failure": {"message": "Cloudflare API rate limited", "hostname": "home.example.com"},
    "service_created": {"hostname": "home.example.com", "target": "10.10.10.1:8080", "ssl_mode": "letsencrypt"},
    "service_deleted": {"hostname": "home.example.com"},
    "service_updated": {"hostname": "home.example.com", "old_target": "10.10.10.1:8080", "target": "10.10.10.2:9000"},
    "record_created": {"hostname": "home.example.com", "record_type": "A", "content": "1.2.3.4"},
    "record_deleted": {"hostname": "home.example.com"},
    "record_updated": {"hostname": "home.example.com", "record_type": "A", "content": "5.6.7.8"},
    "ssl_expiry": {"domain": "home.example.com", "days": 7, "expires_at": "2026-10-09"},
    "ssl_renewed": {"hostname": "home.example.com", "count": 1},
    "app_update": {"target_version": "v1.2.0", "image": "ashiepleb/homelab-dns-manager:latest"},
    "zone_synced": {"count": 3},
    "domain_migrated": {"migrated": 2, "target_domain": "example.com"},
    "login_failed": {"username": "admin", "reason": "Invalid password"},
    "user_changed": {"action": "created", "username": "operator"},
    "api_key_changed": {"action": "created", "name": "WebHost"},
    "settings_changed": {"section": "cloudflare"},
    "backup_restored": {"message": "Database restored from backup"},
}


def _hex_to_int(color: str | None) -> int:
    if not color:
        return COLOR_INFO
    c = color.strip().lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", c):
        return COLOR_INFO
    return int(c, 16)


def _toggle_key(event: str) -> str:
    return f"notify_{event}"


def is_event_enabled(cfg: dict, event: str) -> bool:
    key = _toggle_key(event)
    default = EVENT_DEFAULTS.get(event, "false")
    return cfg.get(key, default) == "true"


def build_plain_message(event: str, data: dict) -> str | None:
    builders = {
        "ip_change": lambda d: (
            f"🌐 Public IP changed: {d.get('old_ip', 'unknown')} → {d.get('new_ip')}"
            + (f" ({len(d.get('affected', []))} record(s) updated)" if d.get("affected") else "")
        ),
        "cf_failure": lambda d: f"❌ Cloudflare update failed: {d.get('message', 'Unknown error')}",
        "service_created": lambda d: f"✅ New service: {d.get('hostname', 'unknown')} → {d.get('target', 'unknown')}",
        "service_deleted": lambda d: f"🗑️ Service removed: {d.get('hostname', 'unknown')}",
        "service_updated": lambda d: (
            f"🔧 Service updated: {d.get('hostname', 'unknown')} "
            f"{d.get('old_target', '?')} → {d.get('target', '?')}"
        ),
        "record_created": lambda d: (
            f"📝 New DNS record: {d.get('hostname', 'unknown')} "
            f"({d.get('record_type', '?')}) → {d.get('content', '')}"
        ),
        "record_deleted": lambda d: f"🗑️ DNS record removed: {d.get('hostname', 'unknown')}",
        "record_updated": lambda d: (
            f"📝 DNS record updated: {d.get('hostname', 'unknown')} "
            f"({d.get('record_type', '?')}) → {d.get('content', '')}"
        ),
        "ssl_expiry": lambda d: (
            f"🔒 SSL certificate expiring soon: {d.get('domain', 'unknown')}"
            + (
                f" ({d.get('days')} days left, expires {d.get('expires_at')})"
                if d.get("days") is not None
                else ""
            )
        ),
        "ssl_renewed": lambda d: (
            "🔐 SSL renew started: "
            + (str(d.get("hostname")) if d.get("hostname") else f"{d.get('count', 0)} certificate(s)")
        ),
        "app_update": lambda d: f"⬆️ App update started → {d.get('target_version') or d.get('image', 'latest')}",
        "zone_synced": lambda d: f"☁️ Cloudflare zones synced ({d.get('count', 0)} zone(s))",
        "domain_migrated": lambda d: (
            f"📦 Migrated {d.get('migrated', 0)} service(s) → {d.get('target_domain', 'unknown')}"
        ),
        "login_failed": lambda d: f"🚨 Failed login: {d.get('username', 'unknown')} — {d.get('reason', 'denied')}",
        "user_changed": lambda d: f"👤 User {d.get('action', 'changed')}: {d.get('username', 'unknown')}",
        "api_key_changed": lambda d: f"🔑 API key {d.get('action', 'changed')}: {d.get('name', 'unknown')}",
        "settings_changed": lambda d: f"⚙️ Settings updated: {d.get('section', 'general')}",
        "backup_restored": lambda d: f"💾 Backup restored: {d.get('message', 'OK')}",
    }
    fn = builders.get(event)
    return fn(data) if fn else None


def build_embed(event: str, data: dict, accent: str | None = None) -> dict | None:
    """Built-in rich embed per event. Accent used for informational events."""
    accent_int = _hex_to_int(accent or DEFAULT_ACCENT)
    plain = build_plain_message(event, data)
    if not plain:
        return None

    # Strip leading emoji for embed title cleanliness
    title_map = {
        "ip_change": ("Public IP changed", COLOR_WARNING),
        "cf_failure": ("Cloudflare update failed", COLOR_ERROR),
        "service_created": ("New service", COLOR_SUCCESS),
        "service_deleted": ("Service removed", COLOR_WARNING),
        "service_updated": ("Service updated", accent_int),
        "record_created": ("DNS record created", COLOR_SUCCESS),
        "record_deleted": ("DNS record removed", COLOR_WARNING),
        "record_updated": ("DNS record updated", accent_int),
        "ssl_expiry": ("SSL certificate expiring", COLOR_WARNING),
        "ssl_renewed": ("SSL certificate renew", accent_int),
        "app_update": ("App update", accent_int),
        "zone_synced": ("Zones synced", accent_int),
        "domain_migrated": ("Domain migration", accent_int),
        "login_failed": ("Failed login attempt", COLOR_ERROR),
        "user_changed": ("User account change", accent_int),
        "api_key_changed": ("API key change", accent_int),
        "settings_changed": ("Settings updated", accent_int),
        "backup_restored": ("Backup restored", COLOR_WARNING),
    }
    title, color = title_map.get(event, (event.replace("_", " ").title(), accent_int))

    fields: list[dict] = []

    def add(name: str, value: Any, inline: bool = True):
        if value is None or value == "":
            return
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value) or "—"
        fields.append({"name": name, "value": str(value)[:1024], "inline": inline})

    if event == "ip_change":
        add("Old IP", data.get("old_ip"))
        add("New IP", data.get("new_ip"))
        add("Records", len(data.get("affected") or []), inline=False)
    elif event in ("service_created", "service_updated"):
        add("Hostname", data.get("hostname"), inline=False)
        add("Target", data.get("target") or data.get("new_target"))
        if data.get("old_target"):
            add("Previous", data.get("old_target"))
        if data.get("ssl_mode"):
            add("SSL", data.get("ssl_mode"))
    elif event == "service_deleted":
        add("Hostname", data.get("hostname"), inline=False)
    elif event in ("record_created", "record_updated"):
        add("Hostname", data.get("hostname"), inline=False)
        add("Type", data.get("record_type"))
        add("Content", data.get("content"), inline=False)
    elif event == "record_deleted":
        add("Hostname", data.get("hostname"), inline=False)
    elif event == "ssl_expiry":
        add("Hostname", data.get("domain"), inline=False)
        add("Days left", data.get("days"))
        add("Expires", data.get("expires_at"))
    elif event == "ssl_renewed":
        add("Hostname", data.get("hostname"))
        add("Count", data.get("count"))
    elif event == "app_update":
        add("Version", data.get("target_version"))
        add("Image", data.get("image"), inline=False)
    elif event == "zone_synced":
        add("Zones", data.get("count"))
    elif event == "domain_migrated":
        add("Migrated", data.get("migrated"))
        add("Target domain", data.get("target_domain"), inline=False)
    elif event == "login_failed":
        add("Username", data.get("username"))
        add("Reason", data.get("reason"), inline=False)
    elif event == "user_changed":
        add("Action", data.get("action"))
        add("Username", data.get("username"))
    elif event == "api_key_changed":
        add("Action", data.get("action"))
        add("Name", data.get("name"))
    elif event == "settings_changed":
        add("Section", data.get("section"), inline=False)
    elif event == "backup_restored":
        add("Details", data.get("message"), inline=False)
    elif event == "cf_failure":
        add("Hostname", data.get("hostname"))
        add("Error", data.get("message"), inline=False)

    embed: dict[str, Any] = {
        "title": title,
        "description": plain,
        "color": color,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": "HomeLab DNS Manager"},
    }
    if fields:
        embed["fields"] = fields
    return embed


async def send_discord_webhook(
    webhook_url: str,
    content: str | None = None,
    embed: dict | None = None,
    username: str | None = None,
):
    payload: dict[str, Any] = {}
    if content:
        payload["content"] = content
    if embed:
        payload["embeds"] = [embed]
    if username and username.strip():
        payload["username"] = username.strip()[:80]
    if not payload.get("content") and not payload.get("embeds"):
        payload["content"] = "HomeLab DNS Manager notification"
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
    if event not in EVENT_DEFAULTS:
        return
    if not is_event_enabled(cfg, event):
        return

    message = build_plain_message(event, data)
    if not message:
        return

    fmt = (cfg.get("discord_format") or "embed").strip().lower()
    if fmt not in ("plain", "embed"):
        fmt = "embed"
    username = cfg.get("discord_username") or None
    accent = cfg.get("discord_accent_color") or DEFAULT_ACCENT

    webhook = cfg.get("discord_webhook")
    if webhook:
        try:
            if fmt == "embed":
                embed = build_embed(event, data, accent=accent)
                await send_discord_webhook(webhook, content=None, embed=embed, username=username)
            else:
                await send_discord_webhook(webhook, content=message, username=username)
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


async def send_test_notification(db: AsyncSession, event: str = "service_created") -> list[dict]:
    """Send a test notification for an event using sample data (ignores toggles)."""
    cfg = await get_settings_dict(db, "notify.")
    results: list[dict] = []
    if event not in EVENT_DEFAULTS:
        event = "service_created"
    data = SAMPLE_DATA.get(event, SAMPLE_DATA["service_created"])
    message = build_plain_message(event, data) or "Test notification"
    fmt = (cfg.get("discord_format") or "embed").strip().lower()
    username = cfg.get("discord_username") or None
    accent = cfg.get("discord_accent_color") or DEFAULT_ACCENT

    webhook = cfg.get("discord_webhook")
    if webhook:
        try:
            if fmt == "embed":
                embed = build_embed(event, data, accent=accent)
                await send_discord_webhook(webhook, content=None, embed=embed, username=username)
            else:
                await send_discord_webhook(webhook, content=f"🧪 Test — {message}", username=username)
            results.append({"channel": "discord", "status": "ok", "event": event, "format": fmt})
        except Exception as e:
            results.append({"channel": "discord", "status": "error", "message": str(e)})
    else:
        results.append({"channel": "discord", "status": "skipped", "message": "Webhook not configured"})

    if cfg.get("smtp_host") and cfg.get("smtp_to"):
        try:
            await send_email(
                cfg["smtp_host"],
                int(cfg.get("smtp_port", "587")),
                cfg.get("smtp_username", ""),
                cfg.get("smtp_password", ""),
                cfg.get("smtp_from", ""),
                cfg["smtp_to"],
                f"HomeLab DNS Manager Test: {event}",
                f"Test notification\n\n{message}",
            )
            results.append({"channel": "email", "status": "ok", "event": event})
        except Exception as e:
            results.append({"channel": "email", "status": "error", "message": str(e)})

    return results


def preview_embed(event: str, accent: str | None = None, data: dict | None = None) -> dict | None:
    """Return embed JSON for UI preview (no network)."""
    sample = data or SAMPLE_DATA.get(event) or SAMPLE_DATA["service_created"]
    return build_embed(event, sample, accent=accent or DEFAULT_ACCENT)
