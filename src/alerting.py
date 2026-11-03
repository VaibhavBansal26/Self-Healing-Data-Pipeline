from __future__ import annotations

import json
import os
from typing import Any, Dict
from urllib import request


def send_alert(
    component: str,
    severity: str,
    message: str,
    metadata: Dict[str, Any] | None = None,
    channel: str = "dashboard",
) -> Dict[str, Any]:
    payload = {
        "component": component,
        "severity": severity,
        "message": message,
        "metadata": metadata or {},
        "channel": channel,
    }
    webhook = os.getenv("ALERT_WEBHOOK_URL", "")
    delivered = False
    error = None
    if webhook and channel in {"slack", "webhook"}:
        try:
            data = json.dumps(
                {"text": f"[{severity.upper()}] {component}: {message}"}
            ).encode("utf-8")
            req = request.Request(
                webhook, data=data, headers={"Content-Type": "application/json"}
            )
            with request.urlopen(req, timeout=5) as resp:
                delivered = 200 <= resp.status < 300
        except Exception as exc:
            error = str(exc)
    try:
        from src.db import get_db_connection

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO alert_events(component,severity,message,channel,delivered,metadata) VALUES(%s,%s,%s,%s,%s,%s);""",
                    (
                        component,
                        severity,
                        message,
                        channel,
                        delivered,
                        json.dumps(metadata or {}),
                    ),
                )
    except Exception:
        pass
    return {**payload, "delivered": delivered, "error": error}


def list_alerts(limit: int = 50):
    try:
        from src.db import get_db_connection

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT alert_id, component, severity, message, channel, delivered, metadata, created_at FROM alert_events ORDER BY created_at DESC LIMIT %s;",
                    (limit,),
                )
                rows = cur.fetchall()
        return [
            {
                "alert_id": r[0],
                "component": r[1],
                "severity": r[2],
                "message": r[3],
                "channel": r[4],
                "delivered": r[5],
                "metadata": r[6],
                "created_at": r[7].isoformat() if r[7] else None,
            }
            for r in rows
        ]
    except Exception as exc:
        return [{"error": str(exc)}]
