import asyncio
import socket


async def check_port(host: str, port: int, timeout: float = 3.0) -> dict:
    """TCP connect check — verifies the target port is reachable from this container."""
    try:
        loop = asyncio.get_event_loop()
        await asyncio.wait_for(
            loop.run_in_executor(None, _tcp_connect, host, port, timeout),
            timeout=timeout + 1,
        )
        return {"host": host, "port": port, "reachable": True, "message": "Port is open"}
    except Exception as e:
        return {
            "host": host,
            "port": port,
            "reachable": False,
            "message": str(e) or "Connection refused or timed out",
        }


def _tcp_connect(host: str, port: int, timeout: float) -> None:
    with socket.create_connection((host, port), timeout=timeout):
        pass
