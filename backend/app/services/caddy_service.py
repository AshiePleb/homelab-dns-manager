"""Generate Caddy config and reload the homelab-caddy container."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import httpx

from app.config import get_settings

settings = get_settings()

CADDY_DIR = Path(os.environ.get("CADDY_CONFIG_DIR", "/app/data/caddy"))
CADDYFILE = CADDY_DIR / "Caddyfile"
CADDY_CONTAINER = os.environ.get("CADDY_CONTAINER", "homelab-caddy")
DOCKER_SOCK = os.environ.get("DOCKER_SOCKET", "/var/run/docker.sock")


def _site_block(hostname: str, forward_host: str, forward_port: int, ssl_mode: str) -> str:
    upstream = f"{forward_host}:{forward_port}"
    return f"""{hostname} {{
    reverse_proxy {upstream}
}}
"""


def write_all_sites(hosts: list[dict]) -> Path:
    """Write Caddyfile from enabled proxy hosts."""
    CADDY_DIR.mkdir(parents=True, exist_ok=True)

    email = settings.acme_email or "admin@localhost"
    lines = [
        "{",
        f"    email {email}",
        "    admin off",
        "}",
        "",
    ]

    for host in hosts:
        if not host.get("enabled", True):
            continue
        lines.append(
            _site_block(
                host["hostname"],
                host["forward_host"],
                host["forward_port"],
                host.get("ssl_mode", "cloudflare"),
            )
        )

    if len(lines) <= 4:
        lines.append(":80 {\n    respond \"HomeLab DNS Manager — no proxy hosts configured\" 200\n}\n")

    CADDYFILE.write_text("\n".join(lines), encoding="utf-8")
    return CADDYFILE


def read_caddyfile() -> str | None:
    if not CADDYFILE.exists():
        return None
    return CADDYFILE.read_text(encoding="utf-8")


def get_container_status() -> dict:
    """Inspect Caddy container via Docker socket."""
    if not os.path.exists(DOCKER_SOCK):
        return {
            "container": CADDY_CONTAINER,
            "running": False,
            "status": "docker_unavailable",
            "message": "Docker socket not mounted",
        }
    try:
        transport = httpx.HTTPTransport(uds=DOCKER_SOCK)
        with httpx.Client(transport=transport, timeout=10.0) as client:
            resp = client.get(f"http://docker/containers/{CADDY_CONTAINER}/json")
            if resp.status_code == 404:
                return {
                    "container": CADDY_CONTAINER,
                    "running": False,
                    "status": "not_found",
                    "message": f"Container {CADDY_CONTAINER} not found",
                }
            resp.raise_for_status()
            data = resp.json()
            state = data.get("State", {})
            return {
                "container": CADDY_CONTAINER,
                "running": bool(state.get("Running")),
                "status": state.get("Status", "unknown"),
                "started_at": state.get("StartedAt"),
                "message": state.get("Status", "unknown"),
            }
    except Exception as e:
        return {
            "container": CADDY_CONTAINER,
            "running": False,
            "status": "error",
            "message": str(e) or "Failed to inspect container",
        }


async def sync_and_reload(db) -> dict:
    """Regenerate Caddyfile from DB and restart Caddy."""
    from sqlalchemy import select
    from app.models import ProxyHost

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
    ok = reload_caddy()
    return {"reloaded": ok, "site_count": len(hosts)}


def reload_caddy() -> bool:
    """Apply Caddyfile by restarting the Caddy container (reliable without docker CLI)."""
    if not CADDYFILE.exists():
        return False
    if not os.path.exists(DOCKER_SOCK):
        return False
    try:
        transport = httpx.HTTPTransport(uds=DOCKER_SOCK)
        with httpx.Client(transport=transport, timeout=60.0) as client:
            resp = client.post(f"http://docker/containers/{CADDY_CONTAINER}/restart")
            resp.raise_for_status()
        return True
    except Exception:
        return False


ACME_ISSUER_LABELS: dict[str, str] = {
    "acme-v02.api.letsencrypt.org-directory": "Let's Encrypt",
    "acme.zerossl.com-v2-dv90": "ZeroSSL",
}


def _cert_file_for_hostname(hostname: str) -> tuple[Path, str] | None:
    """Find on-disk cert for a hostname across all Caddy ACME issuer directories."""
    certs_root = CADDY_DIR / "certificates"
    if not certs_root.is_dir():
        return None

    # Prefer Let's Encrypt when both exist (unusual but deterministic).
    issuer_dirs = sorted(
        (p for p in certs_root.iterdir() if p.is_dir()),
        key=lambda p: (0 if "letsencrypt" in p.name else 1, p.name),
    )
    for issuer_dir in issuer_dirs:
        crt_path = issuer_dir / hostname / f"{hostname}.crt"
        if crt_path.is_file():
            label = ACME_ISSUER_LABELS.get(issuer_dir.name, issuer_dir.name)
            return crt_path, label
    return None


def _cert_dir(hostname: str) -> Path:
    """Legacy path helper — Let's Encrypt directory only."""
    return (
        CADDY_DIR
        / "certificates"
        / "acme-v02.api.letsencrypt.org-directory"
        / hostname
    )


def has_stored_cert(hostname: str) -> bool:
    """Check if Caddy has a stored TLS certificate for this hostname."""
    return _cert_file_for_hostname(hostname) is not None


def has_letsencrypt_cert(hostname: str) -> bool:
    """Alias for has_stored_cert — any Caddy-managed ACME cert."""
    return has_stored_cert(hostname)


def get_cert_issuer(hostname: str) -> str | None:
    found = _cert_file_for_hostname(hostname)
    return found[1] if found else None


def get_cert_expiry(hostname: str) -> dict | None:
    """Parse TLS certificate expiry from Caddy's on-disk store."""
    found = _cert_file_for_hostname(hostname)
    if not found:
        return None
    crt_path, issuer = found
    try:
        from datetime import datetime, timezone

        from cryptography import x509
        from cryptography.hazmat.backends import default_backend

        cert = x509.load_pem_x509_certificate(crt_path.read_bytes(), default_backend())
        expires_at = cert.not_valid_after_utc
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        days_remaining = (expires_at - now).days
        return {
            "expires_at": expires_at,
            "days_remaining": days_remaining,
            "issuer": issuer,
            "path": str(crt_path),
        }
    except Exception:
        return None


def remove_stored_cert(hostname: str) -> bool:
    """Remove on-disk ACME certificates for a hostname (all issuer dirs)."""
    certs_root = CADDY_DIR / "certificates"
    if not certs_root.is_dir():
        return False
    removed = False
    for issuer_dir in certs_root.iterdir():
        if not issuer_dir.is_dir():
            continue
        cert_dir = issuer_dir / hostname
        if cert_dir.is_dir():
            shutil.rmtree(cert_dir, ignore_errors=True)
            removed = True
    return removed


async def probe_https(hostname: str, timeout: float = 4.0) -> tuple[bool, str]:
    """HEAD request to verify HTTPS is reachable."""
    try:
        async with httpx.AsyncClient(timeout=timeout, verify=True) as client:
            resp = await client.head(f"https://{hostname}/", follow_redirects=True)
            if resp.status_code < 500:
                return True, f"HTTPS OK ({resp.status_code})"
            return False, f"HTTPS returned {resp.status_code}"
    except httpx.ConnectError:
        return False, "Connection refused or port 443 not reachable"
    except httpx.ConnectTimeout:
        return False, "HTTPS timed out"
    except Exception as e:
        return False, str(e) or "HTTPS check failed"


async def get_ssl_status(
    hostname: str,
    has_proxy: bool,
    ssl_mode: str | None = None,
    *,
    https_probe: tuple[bool, str] | None = None,
) -> dict:
    """SSL provider and health for a hostname with an optional Caddy proxy.

    Pass https_probe=(ok, message) to reuse an existing HTTPS check and avoid a second probe.
    """
    if not has_proxy:
        return {
            "ssl_provider": None,
            "ssl_mode": None,
            "ssl_status": "none",
            "ssl_label": "—",
            "ssl_message": "DNS only — no Caddy proxy",
        }

    mode = ssl_mode or "letsencrypt"
    issuer = get_cert_issuer(hostname)
    if issuer:
        label = f"Caddy · {issuer}"
    elif mode == "letsencrypt":
        label = "Caddy · Let's Encrypt"
    else:
        label = f"Caddy · {mode}"
    has_cert = has_stored_cert(hostname)
    https_ok, https_msg = https_probe if https_probe is not None else await probe_https(hostname)

    if has_cert and https_ok:
        status, message = "active", https_msg
    elif has_cert:
        status, message = "warning", f"Certificate on disk but probe failed: {https_msg}"
    elif https_ok:
        status, message = "active", https_msg
    else:
        status, message = "pending", "No certificate yet — check ports 80/443 and DNS"

    return {
        "ssl_provider": "caddy",
        "ssl_mode": mode,
        "ssl_status": status,
        "ssl_label": label,
        "ssl_message": message,
    }
