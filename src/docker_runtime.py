from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List

try:
    import docker
    from docker.errors import NotFound
except Exception:  # pragma: no cover
    docker = None
    NotFound = Exception


def _client():
    if docker is None:
        raise RuntimeError("docker_sdk_unavailable")
    return docker.from_env()


def _name_candidates(name: str) -> List[str]:
    # Compose service names and fixed container names used in this project.
    mapping = {
        "consumer": ["healing_consumer", "consumer"],
        "data-api": ["healing_data_api", "data-api"],
        "frontend": ["healing_frontend", "frontend"],
        "metrics": ["healing_metrics", "metrics"],
        "postgres": ["healing_postgres", "postgres"],
        "redis": ["healing_redis", "redis"],
        "kafka": ["healing_kafka", "kafka"],
        "zookeeper": ["healing_zookeeper", "zookeeper"],
        "airflow-webserver": ["healing_airflow_webserver", "airflow-webserver"],
        "airflow-scheduler": ["healing_airflow_scheduler", "airflow-scheduler"],
        "airflow-postgres": ["healing_airflow_postgres", "airflow-postgres"],
        "prometheus": ["healing_prometheus", "prometheus"],
    }
    return mapping.get(name, [name, f"healing_{name.replace('-', '_')}"])


def get_container_status(service_or_container: str) -> Dict[str, Any]:
    """Return real Docker status for a service/container.

    This is intentionally separate from data-plane health checks. A Kafka topic can be
    healthy while the consumer container is stopped; this function catches that case.
    """
    if os.getenv("ENABLE_DOCKER_STATUS", "true").lower() == "false":
        return {
            "service": service_or_container,
            "status": "unknown",
            "running": False,
            "color": "yellow",
            "reason": "docker_status_disabled",
        }
    try:
        client = _client()
        last_error = None
        for name in _name_candidates(service_or_container):
            try:
                container = client.containers.get(name)
                container.reload()
                state = container.status or "unknown"
                attrs_state = (container.attrs or {}).get("State", {})
                health = attrs_state.get("Health", {}).get("Status")
                running = state == "running"
                if running and (health in {None, "healthy"}):
                    semantic_status = "healthy"
                    color = "green"
                    reason = "container_running"
                elif running and health == "starting":
                    semantic_status = "degraded"
                    color = "yellow"
                    reason = "container_health_starting"
                elif running:
                    semantic_status = "degraded"
                    color = "yellow"
                    reason = f"container_running_health_{health}"
                elif state in {"restarting", "created"}:
                    semantic_status = "degraded"
                    color = "yellow"
                    reason = f"container_{state}"
                else:
                    semantic_status = "unhealthy"
                    color = "red"
                    reason = f"container_{state}"
                return {
                    "service": service_or_container,
                    "container": name,
                    "status": semantic_status,
                    "docker_state": state,
                    "health": health,
                    "running": running,
                    "color": color,
                    "reason": reason,
                    "short_id": getattr(container, "short_id", None),
                }
            except Exception as exc:  # keep trying aliases
                last_error = str(exc)
        return {
            "service": service_or_container,
            "status": "unhealthy",
            "docker_state": "missing",
            "running": False,
            "color": "red",
            "reason": "container_missing_or_unreachable",
            "error": last_error,
        }
    except Exception as exc:
        return {
            "service": service_or_container,
            "status": "unknown",
            "docker_state": "unknown",
            "running": False,
            "color": "yellow",
            "reason": "docker_socket_unavailable",
            "error": str(exc),
            "hint": "Mount /var/run/docker.sock into data-api and install docker Python SDK.",
        }


def get_many_container_statuses(services: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    return {name: get_container_status(name) for name in services}


def _recovery_allowed() -> bool:
    return os.getenv("ENABLE_DOCKER_RECOVERY", "false").lower() == "true"


def start_container(service_or_container: str) -> Dict[str, Any]:
    if not _recovery_allowed():
        return {"ok": False, "dry_run": True, "service": service_or_container, "reason": "ENABLE_DOCKER_RECOVERY is not true"}
    try:
        client = _client()
        last_error = None
        for name in _name_candidates(service_or_container):
            try:
                container = client.containers.get(name)
                container.start()
                container.reload()
                return {"ok": True, "service": service_or_container, "container": name, "status": container.status}
            except Exception as exc:
                last_error = str(exc)
        return {"ok": False, "service": service_or_container, "reason": "container_not_found", "error": last_error}
    except Exception as exc:
        return {"ok": False, "service": service_or_container, "reason": "docker_start_failed", "error": str(exc)}


def restart_container(service_or_container: str) -> Dict[str, Any]:
    if not _recovery_allowed():
        return {"ok": False, "dry_run": True, "service": service_or_container, "reason": "ENABLE_DOCKER_RECOVERY is not true"}
    try:
        client = _client()
        last_error = None
        for name in _name_candidates(service_or_container):
            try:
                container = client.containers.get(name)
                container.restart(timeout=15)
                container.reload()
                return {"ok": True, "service": service_or_container, "container": name, "status": container.status}
            except Exception as exc:
                last_error = str(exc)
        return {"ok": False, "service": service_or_container, "reason": "container_not_found", "error": last_error}
    except Exception as exc:
        return {"ok": False, "service": service_or_container, "reason": "docker_restart_failed", "error": str(exc)}


def container_logs(service_or_container: str, tail: int = 120) -> Dict[str, Any]:
    try:
        client = _client()
        last_error = None
        for name in _name_candidates(service_or_container):
            try:
                container = client.containers.get(name)
                logs = container.logs(tail=tail).decode("utf-8", errors="replace")
                return {"ok": True, "service": service_or_container, "container": name, "logs": logs[-8000:]}
            except Exception as exc:
                last_error = str(exc)
        return {"ok": False, "service": service_or_container, "reason": "container_not_found", "error": last_error}
    except Exception as exc:
        return {"ok": False, "service": service_or_container, "reason": "docker_logs_failed", "error": str(exc)}
