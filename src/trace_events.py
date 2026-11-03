from __future__ import annotations

import json
from typing import Any, Dict


def trace_event(
    trace_name: str,
    stage: str,
    status: str,
    latency_ms: int = 0,
    metadata: Dict[str, Any] | None = None,
) -> None:
    try:
        from src.db import get_db_connection

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO pipeline_trace_events(trace_name,stage,status,latency_ms,metadata) VALUES(%s,%s,%s,%s,%s);""",
                    (trace_name, stage, status, latency_ms, json.dumps(metadata or {})),
                )
    except Exception:
        pass


def list_trace_events(limit: int = 100):
    try:
        from src.db import get_db_connection

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT trace_id, trace_name, stage, status, latency_ms, metadata, created_at FROM pipeline_trace_events ORDER BY created_at DESC LIMIT %s;",
                    (limit,),
                )
                rows = cur.fetchall()
        return [
            {
                "trace_id": r[0],
                "trace_name": r[1],
                "stage": r[2],
                "status": r[3],
                "latency_ms": r[4],
                "metadata": r[5],
                "created_at": r[6].isoformat() if r[6] else None,
            }
            for r in rows
        ]
    except Exception as exc:
        return [{"error": str(exc)}]
