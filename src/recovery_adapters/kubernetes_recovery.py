from __future__ import annotations

from typing import Any, Dict


def restart_deployment(deployment: str, namespace: str = "default") -> Dict[str, Any]:
    # Safe blueprint adapter. It returns the kubectl command unless a production operator enables execution separately.
    return {"ok": False, "dry_run": True, "command": ["kubectl", "rollout", "restart", "deployment", deployment, "-n", namespace]}


def scale_deployment(deployment: str, replicas: int, namespace: str = "default") -> Dict[str, Any]:
    return {"ok": False, "dry_run": True, "command": ["kubectl", "scale", "deployment", deployment, f"--replicas={replicas}", "-n", namespace]}


def read_pod_logs(selector: str, namespace: str = "default", tail: int = 200) -> Dict[str, Any]:
    return {"ok": False, "dry_run": True, "command": ["kubectl", "logs", "-l", selector, "-n", namespace, "--tail", str(tail)]}
