"""Compare running image version with Docker Hub."""

from __future__ import annotations

import os
from datetime import datetime, timezone

import httpx

DEFAULT_REPO = "ashiepleb/homelab-dns-manager"
HUB_API = "https://hub.docker.com/v2/repositories/{repo}/tags/{tag}"


def _parse_hub_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


async def fetch_hub_tag(repo: str, tag: str) -> dict | None:
    url = HUB_API.format(repo=repo, tag=tag)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(url)
            if res.status_code == 404:
                return None
            res.raise_for_status()
            return res.json()
    except Exception:
        return None


async def get_version_status() -> dict:
    repo = os.getenv("DOCKER_IMAGE_REPO", DEFAULT_REPO)
    version = os.getenv("APP_VERSION", "dev")
    build_time_raw = os.getenv("BUILD_TIME", "")
    build_time = _parse_hub_time(build_time_raw)

    latest = await fetch_hub_tag(repo, "latest")
    latest_published = _parse_hub_time(latest.get("last_updated") if latest else None)

    update_available = False
    if latest_published and build_time:
        update_available = latest_published > build_time
    elif latest_published and version in ("dev", "unknown", ""):
        update_available = True

    return {
        "version": version,
        "build_time": build_time_raw or None,
        "image": f"{repo}:{version}",
        "docker_hub_repo": repo,
        "latest_tag": "latest",
        "latest_published_at": latest_published.isoformat() if latest_published else None,
        "update_available": update_available,
        "check_ok": latest is not None,
    }
