from __future__ import annotations

from typing import Any, Dict


def rerun_reconciliation() -> Dict[str, Any]:
    from src.reconciliation import run_reconciliation

    return {"ok": True, "action": "run_reconciliation", "result": run_reconciliation()}


def airflow_health_summary() -> Dict[str, Any]:
    try:
        from src.db import get_db_connection

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*), MAX(created_at) FROM reconciliation_runs;"
                )
                count, latest = cur.fetchone()
        return {
            "ok": True,
            "reconciliation_runs": count,
            "latest_run": latest.isoformat() if latest else None,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
