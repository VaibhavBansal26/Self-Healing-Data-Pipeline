from __future__ import annotations

from typing import Any, Dict

from src.docker_runtime import (
    container_logs,
    get_container_status,
    restart_container,
    start_container,
)


def restart_service(service: str) -> Dict[str, Any]:
    """Restart a local Docker service/container through the Docker socket.

    Safe by default: actual restart requires ENABLE_DOCKER_RECOVERY=true.
    """
    before = get_container_status(service)
    result = restart_container(service)
    after = get_container_status(service)
    return {
        "ok": bool(result.get("ok")),
        "before": before,
        "action_result": result,
        "after": after,
    }


def start_service(service: str) -> Dict[str, Any]:
    before = get_container_status(service)
    result = start_container(service)
    after = get_container_status(service)
    return {
        "ok": bool(result.get("ok")),
        "before": before,
        "action_result": result,
        "after": after,
    }


def service_logs(service: str, tail: int = 120) -> Dict[str, Any]:
    return container_logs(service, tail=tail)


def service_status(service: str) -> Dict[str, Any]:
    return get_container_status(service)
