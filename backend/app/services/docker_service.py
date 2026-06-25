from datetime import datetime, timezone
import docker
from docker.errors import DockerException

from app.config import get_settings

settings = get_settings()


def _get_client():
    return docker.DockerClient(base_url=f"unix://{settings.docker_socket}")


def _format_uptime(started_at: str | None) -> str | None:
    if not started_at:
        return None
    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - start
        days = delta.days
        hours, rem = divmod(delta.seconds, 3600)
        minutes, _ = divmod(rem, 60)
        if days:
            return f"{days}d {hours}h"
        if hours:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"
    except Exception:
        return None


def list_containers() -> list[dict]:
    try:
        client = _get_client()
        containers = client.containers.list(all=True)
        result = []
        for c in containers:
            ports = []
            if c.ports:
                for port, bindings in c.ports.items():
                    if bindings:
                        for b in bindings:
                            ports.append(f"{b.get('HostIp', '0.0.0.0')}:{b['HostPort']}->{port}")
                    else:
                        ports.append(port)
            result.append({
                "id": c.short_id,
                "name": c.name,
                "image": c.image.tags[0] if c.image.tags else c.image.short_id,
                "status": c.status,
                "state": c.attrs.get("State", {}).get("Status", c.status),
                "ports": ports,
                "uptime": _format_uptime(c.attrs.get("State", {}).get("StartedAt")),
            })
        return result
    except DockerException as e:
        return [{"id": "error", "name": "Docker unavailable", "image": "", "status": "error", "state": str(e), "ports": [], "uptime": None}]


def container_action(container_id: str, action: str) -> dict:
    client = _get_client()
    container = client.containers.get(container_id)
    if action == "start":
        container.start()
    elif action == "stop":
        container.stop()
    elif action == "restart":
        container.restart()
    else:
        raise ValueError(f"Unknown action: {action}")
    container.reload()
    return {"id": container.short_id, "status": container.status}


def get_container_logs(container_id: str, tail: int = 100) -> str:
    client = _get_client()
    container = client.containers.get(container_id)
    return container.logs(tail=tail).decode("utf-8", errors="replace")


def get_container_details(container_id: str) -> dict:
    client = _get_client()
    container = client.containers.get(container_id)
    return {
        "id": container.short_id,
        "name": container.name,
        "image": container.image.tags[0] if container.image.tags else container.image.short_id,
        "status": container.status,
        "created": container.attrs.get("Created"),
        "env": container.attrs.get("Config", {}).get("Env", []),
        "mounts": container.attrs.get("Mounts", []),
        "network": container.attrs.get("NetworkSettings", {}),
    }


def count_running() -> int:
    try:
        client = _get_client()
        return len(client.containers.list(filters={"status": "running"}))
    except DockerException:
        return 0
