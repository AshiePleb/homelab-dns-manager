"""Compare running image version with Docker Hub semver tags."""

from __future__ import annotations

import os
import re
import time
from datetime import datetime

import docker
import httpx
from docker.errors import DockerException, ImageNotFound

DEFAULT_REPO = "ashiepleb/homelab-dns-manager"
HUB_TAG_API = "https://hub.docker.com/v2/repositories/{repo}/tags/{tag}"
HUB_TAGS_API = "https://hub.docker.com/v2/repositories/{repo}/tags"
SEMVER_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")

# Cache Hub lookups — every page load was hitting Docker Hub and slowing the UI.
_VERSION_CACHE: dict | None = None
_VERSION_CACHE_AT = 0.0
_VERSION_CACHE_TTL = 300.0


def _parse_hub_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_semver(tag: str) -> tuple[int, int, int] | None:
    tag = tag.strip()
    m = SEMVER_TAG.match(tag if tag.startswith("v") else f"v{tag}")
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def normalize_version_tag(version: str) -> str:
    version = (version or "").strip()
    if not version or version in ("dev", "unknown", "latest"):
        return version
    return version if version.startswith("v") else f"v{version}"


async def fetch_hub_tag(repo: str, tag: str) -> dict | None:
    url = HUB_TAG_API.format(repo=repo, tag=tag)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(url)
            if res.status_code == 404:
                return None
            res.raise_for_status()
            return res.json()
    except Exception:
        return None


async def fetch_latest_semver_tag(repo: str) -> dict | None:
    """Return metadata for the newest vX.Y.Z tag on Docker Hub."""
    best: tuple[tuple[int, int, int], dict] | None = None
    url: str | None = HUB_TAGS_API.format(repo=repo) + "?page_size=100&ordering=-last_updated"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            while url:
                res = await client.get(url)
                res.raise_for_status()
                data = res.json()
                for item in data.get("results", []):
                    name = item.get("name", "")
                    parsed = parse_semver(name)
                    if not parsed:
                        continue
                    if best is None or parsed > best[0]:
                        best = (parsed, item)
                url = data.get("next")
    except Exception:
        return None
    if not best:
        return None
    tag_name = best[1].get("name", "")
    return {
        "tag": normalize_version_tag(tag_name),
        "published_at": _parse_hub_time(best[1].get("last_updated")),
        "digest": best[1].get("digest"),
    }


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
    global _VERSION_CACHE, _VERSION_CACHE_AT
    now = time.monotonic()
    if _VERSION_CACHE is not None and (now - _VERSION_CACHE_AT) < _VERSION_CACHE_TTL:
        return _VERSION_CACHE

    repo = os.getenv("DOCKER_IMAGE_REPO", DEFAULT_REPO)
    raw_version = os.getenv("APP_VERSION", "dev")
    version = normalize_version_tag(raw_version)
    build_time_raw = os.getenv("BUILD_TIME", "")
    running_semver = parse_semver(version)

    latest_info = await fetch_latest_semver_tag(repo)
    latest_version = latest_info["tag"] if latest_info else None
    latest_published = latest_info["published_at"] if latest_info else None
    hub_digest = latest_info.get("digest") if latest_info else None

    latest_tag_meta = await fetch_hub_tag(repo, "latest") if not hub_digest else None
    if latest_tag_meta and not hub_digest:
        hub_digest = latest_tag_meta.get("digest")

    local_digest = _local_image_digest(repo, "latest")

    update_available = False
    if running_semver and latest_info:
        latest_semver = parse_semver(latest_version or "")
        if latest_semver:
            update_available = running_semver < latest_semver
    elif version in ("dev", "unknown", "latest", ""):
        update_available = latest_version is not None
    elif local_digest and hub_digest:
        update_available = local_digest != hub_digest

    status = {
        "version": version if version else raw_version,
        "build_time": build_time_raw or None,
        "image": f"{repo}:{version or raw_version}",
        "docker_hub_repo": repo,
        "latest_tag": latest_version or "latest",
        "latest_version": latest_version,
        "latest_published_at": latest_published.isoformat() if latest_published else None,
        "update_available": update_available,
        "check_ok": latest_info is not None,
        "image_digest": local_digest,
        "latest_digest": hub_digest,
    }
    _VERSION_CACHE = status
    _VERSION_CACHE_AT = now
    return status
