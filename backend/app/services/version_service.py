"""Compare running image version with Docker Hub."""

from __future__ import annotations

import os
from datetime import datetime, timedelta

import docker
import httpx
from docker.errors import DockerException, ImageNotFound

DEFAULT_REPO = "ashiepleb/homelab-dns-manager"
HUB_API = "https://hub.docker.com/v2/repositories/{repo}/tags/{tag}"
# Hub `last_updated` is when the push finished — often a minute after build started.
UPDATE_GRACE = timedelta(minutes=15)


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


def _local_image_digest(repo: str, tag: str = "latest") -> str | None:
    socket = os.getenv("DOCKER_SOCKET", "/var/run/docker.sock")
    refs = (
        f"{repo}:{tag}",
        f"docker.io/{repo}:{tag}",
        f"index.docker.io/{repo}:{tag}",
    )
    try:
        client = docker.DockerClient(base_url=f"unix://{socket}")
        for ref in refs:
            try:
                img = client.images.get(ref)
            except ImageNotFound:
                continue
            for digest in img.attrs.get("RepoDigests") or []:
                if "@sha256:" in digest:
                    return digest.split("@", 1)[1]
    except (DockerException, OSError):
        pass
    return None


async def get_version_status() -> dict:
    repo = os.getenv("DOCKER_IMAGE_REPO", DEFAULT_REPO)
    version = os.getenv("APP_VERSION", "dev")
    build_time_raw = os.getenv("BUILD_TIME", "")
    build_time = _parse_hub_time(build_time_raw)
    latest_tag = "latest"

    latest = await fetch_hub_tag(repo, latest_tag)
    latest_published = _parse_hub_time(latest.get("last_updated") if latest else None)
    hub_digest = (latest or {}).get("digest")
    local_digest = _local_image_digest(repo, latest_tag)

    update_available = False
    if local_digest and hub_digest:
        update_available = local_digest != hub_digest
    elif latest_published and build_time:
        update_available = latest_published - build_time > UPDATE_GRACE
    elif latest_published and version in ("dev", "unknown", ""):
        update_available = True

    return {
        "version": version,
        "build_time": build_time_raw or None,
        "image": f"{repo}:{version}",
        "docker_hub_repo": repo,
        "latest_tag": latest_tag,
        "latest_published_at": latest_published.isoformat() if latest_published else None,
        "update_available": update_available,
        "check_ok": latest is not None,
        "image_digest": local_digest,
        "latest_digest": hub_digest,
    }
