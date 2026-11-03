from __future__ import annotations

from typing import Any, Dict


def create_approval_request(
    component: str,
    proposed_action: str,
    risk_level: str,
    agent_reason: str,
    step_incident_id: int | None = None,
    event_id: str | None = None,
) -> Dict[str, Any]:
    from src.db import get_db_connection

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO human_approval_requests(step_incident_id,component,event_id,proposed_action,risk_level,agent_reason,status) VALUES(%s,%s,%s,%s,%s,%s,'pending') RETURNING approval_id;""",
                (
                    step_incident_id,
                    component,
                    event_id,
                    proposed_action,
                    risk_level,
                    agent_reason,
                ),
            )
            approval_id = cur.fetchone()[0]
    return {
        "approval_id": approval_id,
        "component": component,
        "proposed_action": proposed_action,
        "status": "pending",
    }


def find_pending_approval(
    component: str, proposed_action: str
) -> Dict[str, Any] | None:
    """The open approval request for this component and action, if there is one.

    The healer runs every few seconds; without this it files a new request for the
    same unresolved problem on every cycle.
    """
    from src.db import get_db_connection

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT approval_id, step_incident_id FROM human_approval_requests
                WHERE component=%s AND proposed_action=%s AND status='pending'
                ORDER BY created_at DESC LIMIT 1;""",
                (component, proposed_action),
            )
            row = cur.fetchone()
    if not row:
        return None
    return {
        "approval_id": row[0],
        "step_incident_id": row[1],
        "component": component,
        "proposed_action": proposed_action,
        "status": "pending",
    }


def decide_approval(
    approval_id: int, status: str, reviewer: str = "dashboard", reviewer_notes: str = ""
) -> Dict[str, Any]:
    if status not in {"approved", "rejected", "closed"}:
        raise ValueError("status must be approved, rejected, or closed")
    from src.db import get_db_connection

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE human_approval_requests SET status=%s, reviewer=%s, reviewer_notes=%s, decided_at=CURRENT_TIMESTAMP WHERE approval_id=%s RETURNING approval_id, step_incident_id, component, proposed_action, status;""",
                (status, reviewer, reviewer_notes, approval_id),
            )
            row = cur.fetchone()

    if not row:
        return {"approval_id": approval_id, "updated": False, "status": "missing"}

    response = {
        "approval_id": row[0],
        "step_incident_id": row[1],
        "component": row[2],
        "proposed_action": row[3],
        "status": row[4],
        "updated": True,
    }

    # When an operator approves a pipeline-level recovery, execute the approved
    # action immediately and return the result. This prevents the UI from leaving
    # an approved item in a confusing pending-looking state.
    if status == "approved":
        try:
            from src.pipeline_health import heal_pipeline_component

            response["execution_result"] = heal_pipeline_component(
                row[2], row[3], approve_risky=True
            )
        except Exception as exc:
            response["execution_result"] = {
                "status": "execution_failed",
                "error": str(exc),
            }
    return response


def list_approval_requests(limit: int = 100, status: str = "all"):
    from src.db import get_db_connection

    where = "" if status == "all" else "WHERE status = %s"
    params = [] if status == "all" else [status]
    params.append(limit)
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT approval_id, step_incident_id, component, event_id, proposed_action, risk_level, agent_reason, status, reviewer, reviewer_notes, created_at, decided_at FROM human_approval_requests {where} ORDER BY created_at DESC LIMIT %s;""",
                params,
            )
            rows = cur.fetchall()
    return [
        {
            "approval_id": r[0],
            "step_incident_id": r[1],
            "component": r[2],
            "event_id": r[3],
            "proposed_action": r[4],
            "risk_level": r[5],
            "agent_reason": r[6],
            "status": r[7],
            "reviewer": r[8],
            "reviewer_notes": r[9],
            "created_at": r[10].isoformat() if r[10] else None,
            "decided_at": r[11].isoformat() if r[11] else None,
        }
        for r in rows
    ]
