"""Self-update: pull Docker Hub image and recreate this container."""

from __future__ import annotations

import logging
import os
import threading
import time

import docker
from docker.errors import DockerException, ImageNotFound, NotFound

from app.config import get_settings
from app.services.version_service import DEFAULT_REPO, get_version_status

logger = logging.getLogger(__name__)
settings = get_settings()

APP_CONTAINER_NAME = os.getenv("APP_CONTAINER_NAME", "homelab-dns-manager")


def _client() -> docker.DockerClient:
    return docker.DockerClient(base_url=f"unix://{settings.docker_socket}")


def _mounts_for_create(inspect_mounts: list[dict] | None) -> list[dict]:
    mounts: list[dict] = []
    for m in inspect_mounts or []:
        mtype = m.get("Type") or "bind"
        source = m.get("Name") if mtype == "volume" else m.get("Source")
        target = m.get("Destination")
        if not source or not target:
            continue
        mounts.append(
            {
                "Type": mtype,
                "Source": source,
                "Target": target,
                "ReadOnly": not m.get("RW", True),
            }
        )
    return mounts


def pull_app_image(image: str) -> str:
    """Pull image; returns the resolved image ref."""
    client = _client()
    if ":" in image:
        repo, tag = image.rsplit(":", 1)
    else:
        repo, tag = image, "latest"
    logger.info("Pulling %s:%s", repo, tag)
    client.images.pull(repo, tag=tag)
    return f"{repo}:{tag}"


def _recreate_container(image: str) -> None:
    client = _client()
    try:
        old = client.containers.get(APP_CONTAINER_NAME)
    except NotFound:
        # Fall back to this process's container ID (HOSTNAME in Docker)
        hostname = os.getenv("HOSTNAME", "")
        if not hostname:
            raise RuntimeError(f"Container {APP_CONTAINER_NAME} not found")
        old = client.containers.get(hostname)

    attrs = old.attrs
    config = attrs.get("Config") or {}
    host_raw = attrs.get("HostConfig") or {}
    name = old.name.lstrip("/")
    backup_name = f"{name}-pre-update"

    # Free the name for the new container
    try:
        existing_backup = client.containers.get(backup_name)
        existing_backup.remove(force=True)
    except NotFound:
        pass
    except DockerException:
        pass

    try:
        old.rename(backup_name)
    except DockerException as e:
        logger.warning("Could not rename container before update: %s", e)

    try:
        old.stop(timeout=25)
    except DockerException as e:
        logger.warning("Stop before recreate: %s", e)

    mounts = _mounts_for_create(attrs.get("Mounts"))
    network_mode = host_raw.get("NetworkMode") or "default"
    # Compose attaches custom networks; avoid conflicting network_mode + networking_config
    use_custom_networks = bool(attrs.get("NetworkSettings", {}).get("Networks")) and network_mode not in (
        "host",
        "none",
    )

    host_config = client.api.create_host_config(
        binds=None if mounts else host_raw.get("Binds"),
        mounts=mounts or None,
        port_bindings=host_raw.get("PortBindings"),
        restart_policy=host_raw.get("RestartPolicy") or {"Name": "unless-stopped"},
        privileged=bool(host_raw.get("Privileged")),
        extra_hosts=host_raw.get("ExtraHosts"),
        volumes_from=host_raw.get("VolumesFrom"),
        dns=host_raw.get("Dns"),
        dns_search=host_raw.get("DnsSearch"),
        cap_add=host_raw.get("CapAdd"),
        cap_drop=host_raw.get("CapDrop"),
        devices=host_raw.get("Devices"),
        security_opt=host_raw.get("SecurityOpt"),
        group_add=host_raw.get("GroupAdd"),
        sysctls=host_raw.get("Sysctls") or None,
        shm_size=host_raw.get("ShmSize") or None,
        network_mode=None if use_custom_networks else network_mode,
    )

    networking_config = None
    if use_custom_networks:
        endpoints = {}
        for net_name, net_cfg in (attrs.get("NetworkSettings", {}).get("Networks") or {}).items():
            endpoints[net_name] = client.api.create_endpoint_config(
                aliases=net_cfg.get("Aliases"),
            )
        if endpoints:
            networking_config = client.api.create_networking_config(endpoints)

    # Drop hostname so Docker assigns a fresh one (avoids stale ID hostname)
    create_kwargs = {
        "image": image,
        "name": name,
        "environment": config.get("Env"),
        "labels": config.get("Labels"),
        "command": config.get("Cmd"),
        "entrypoint": config.get("Entrypoint"),
        "working_dir": config.get("WorkingDir") or None,
        "user": config.get("User") or None,
        "host_config": host_config,
        "networking_config": networking_config,
        "domainname": config.get("Domainname") or None,
        "stop_signal": config.get("StopSignal") or None,
        "healthcheck": config.get("Healthcheck"),
    }
    # Remove empty/null optional keys that docker API rejects
    create_kwargs = {k: v for k, v in create_kwargs.items() if v is not None}

    try:
        new = client.api.create_container(**create_kwargs)
        client.api.start(new.get("Id") or new)
        logger.info("Started updated container %s from %s", name, image)
    except Exception:
        logger.exception("Failed to create updated container — attempting to restore previous")
        try:
            old.start()
            try:
                old.rename(name)
            except DockerException:
                pass
        except Exception:
            logger.exception("Failed to restore previous container")
        raise

    try:
        old.remove(force=True)
    except DockerException as e:
        logger.warning("Could not remove pre-update container: %s", e)


def schedule_self_update(image: str) -> None:
    """Pull is assumed done; recreate after a short delay so HTTP can respond."""

    def _run() -> None:
        time.sleep(1.5)
        try:
            _recreate_container(image)
        except Exception:
            logger.exception("Self-update recreate failed")

    threading.Thread(target=_run, name="homelab-self-update", daemon=True).start()


async def start_app_update(*, force: bool = False) -> dict:
    """
    Pull newest image and schedule container recreate.
    Returns immediately; the process will be replaced shortly after.
    """
    status = await get_version_status()
    if not force and not status.get("update_available"):
        raise ValueError("Already up to date")

    repo = os.getenv("DOCKER_IMAGE_REPO", DEFAULT_REPO)
    # Always pull :latest so compose installs stay consistent; also pull semver when known
    latest_image = f"{repo}:latest"
    version_tag = status.get("latest_version")

    try:
        pull_app_image(latest_image)
        if version_tag and version_tag not in ("latest", "dev"):
            try:
                pull_app_image(f"{repo}:{version_tag}")
            except DockerException:
                logger.warning("Optional version tag pull failed for %s", version_tag)
    except ImageNotFound as e:
        raise ValueError(f"Image not found on Docker Hub: {e}") from e
    except DockerException as e:
        raise ValueError(f"Failed to pull image: {e}") from e

    schedule_self_update(latest_image)

    return {
        "status": "restarting",
        "image": latest_image,
        "target_version": version_tag,
        "message": (
            f"Pulled {latest_image}"
            + (f" ({version_tag})" if version_tag else "")
            + ". Restarting the app — this page will reconnect shortly."
        ),
    }
