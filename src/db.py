from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple
from src.config import POSTGRES_CONFIG
from src.idempotency import payload_fingerprint
from src.metrics import DB_INSERT_LATENCY, observe_latency


class IdempotencyConflictError(Exception):
    """Raised when the same event_id arrives with a different payload hash."""


def get_db_connection():
    import psycopg2

    return psycopg2.connect(**POSTGRES_CONFIG)


def insert_order(order):
    event_payload = order.model_dump()
    event_hash = payload_fingerprint(event_payload)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT event_hash FROM orders WHERE event_id = %s;", (order.event_id,)
            )
            row = cur.fetchone()
            if row:
                existing_hash = row[0]
                if existing_hash != event_hash:
                    raise IdempotencyConflictError(
                        f"event_id={order.event_id} already exists with different event_hash"
                    )
                return "duplicate_skipped"

            query = """
            INSERT INTO orders(event_id, event_hash, schema_version, customer_id, amount, currency, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s);
            """
            with observe_latency(DB_INSERT_LATENCY):
                cur.execute(
                    query,
                    (
                        order.event_id,
                        event_hash,
                        order.schema_version,
                        order.customer_id,
                        order.amount,
                        order.currency,
                        order.status,
                    ),
                )
            return "inserted"


def insert_incident(
    original_payload: Dict[str, Any],
    error_type: str,
    error_message: str,
    healed_payload: Optional[Dict[str, Any]] = None,
    healing_action: Optional[str] = None,
    risk_level: Optional[str] = None,
    status: str = "failed",
    confidence: Optional[float] = None,
    agent_trace: Optional[list[Dict[str, Any]]] = None,
    rag_evidence: Optional[list[Dict[str, Any]]] = None,
) -> int:
    query = """
    INSERT INTO pipeline_incidents(
        event_id, event_hash, error_type, error_message, original_payload,
        healed_payload, healing_action, risk_level, confidence, status,
        agent_trace, rag_evidence
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING incident_id;
    """
    event_id = original_payload.get("event_id")
    event_hash = payload_fingerprint(original_payload)
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    event_id,
                    event_hash,
                    error_type,
                    error_message,
                    json.dumps(original_payload),
                    json.dumps(healed_payload) if healed_payload else None,
                    healing_action,
                    risk_level,
                    confidence,
                    status,
                    json.dumps(agent_trace or []),
                    json.dumps(rag_evidence or []),
                ),
            )
            return cur.fetchone()[0]


def insert_replay_audit(
    original_payload: Dict[str, Any],
    replayed_payload: Optional[Dict[str, Any]],
    replay_status: str,
    reviewer: Optional[str] = None,
    reviewer_notes: Optional[str] = None,
    failure_reason: Optional[str] = None,
) -> int:
    query = """
    INSERT INTO dlq_replay_audit(
        event_id, event_hash, original_payload, replayed_payload, replay_status,
        reviewer, reviewer_notes, failure_reason
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING replay_id;
    """
    event_id = original_payload.get("event_id")
    event_hash = payload_fingerprint(original_payload)
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    event_id,
                    event_hash,
                    json.dumps(original_payload),
                    json.dumps(replayed_payload) if replayed_payload else None,
                    replay_status,
                    reviewer,
                    reviewer_notes,
                    failure_reason,
                ),
            )
            return cur.fetchone()[0]


def count_orders_and_incidents() -> Tuple[int, int, int]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM orders;")
            orders_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM pipeline_incidents;")
            incident_count = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM pipeline_incidents WHERE status IN ('failed', 'manual_review');"
            )
            unresolved = cur.fetchone()[0]
    return orders_count, incident_count, unresolved


def insert_reconciliation_run(
    orders_count: int, incident_count: int, dlq_count: int, unresolved: int, notes: str
):
    query = """
    INSERT INTO reconciliation_runs(orders_count, incident_count, dlq_count, unresolved_incident_count, notes)
    VALUES (%s, %s, %s, %s, %s);
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query, (orders_count, incident_count, dlq_count, unresolved, notes)
            )


def insert_pipeline_step_incident(
    component: str,
    problem_type: str,
    reason: str,
    detected_state: Optional[Dict[str, Any]] = None,
    recovery_action: Optional[str] = None,
    verification_result: Optional[Dict[str, Any]] = None,
    risk_level: str = "medium",
    status: str = "detected",
    requires_human_approval: bool = False,
) -> int:
    query = """
    INSERT INTO pipeline_step_incidents(
        component, problem_type, reason, detected_state, recovery_action,
        verification_result, risk_level, status, requires_human_approval
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING step_incident_id;
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    component,
                    problem_type,
                    reason,
                    json.dumps(detected_state or {}),
                    recovery_action,
                    json.dumps(verification_result or {}),
                    risk_level,
                    status,
                    requires_human_approval,
                ),
            )
            return cur.fetchone()[0]


def update_pipeline_step_incident(
    step_incident_id: int,
    status: str,
    recovery_action: Optional[str] = None,
    verification_result: Optional[Dict[str, Any]] = None,
) -> bool:
    query = """
    UPDATE pipeline_step_incidents
    SET status = %s,
        recovery_action = COALESCE(%s, recovery_action),
        verification_result = COALESCE(%s, verification_result),
        updated_at = CURRENT_TIMESTAMP
    WHERE step_incident_id = %s;
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    status,
                    recovery_action,
                    (
                        json.dumps(verification_result)
                        if verification_result is not None
                        else None
                    ),
                    step_incident_id,
                ),
            )
            return cur.rowcount > 0


def list_pipeline_step_incidents(limit: int = 50, status: Optional[str] = None):
    limit = max(1, min(int(limit), 250))
    params: list[Any] = []
    where = ""
    if status and status != "all":
        where = "WHERE status = %s"
        params.append(status)
    query = f"""
    SELECT step_incident_id, component, problem_type, reason, detected_state,
           recovery_action, verification_result, risk_level, status,
           requires_human_approval, created_at, updated_at
    FROM pipeline_step_incidents
    {where}
    ORDER BY created_at DESC
    LIMIT %s;
    """
    params.append(limit)
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
    return [
        {
            "step_incident_id": r[0],
            "component": r[1],
            "problem_type": r[2],
            "reason": r[3],
            "detected_state": r[4],
            "recovery_action": r[5],
            "verification_result": r[6],
            "risk_level": r[7],
            "status": r[8],
            "requires_human_approval": r[9],
            "created_at": r[10].isoformat() if r[10] else None,
            "updated_at": r[11].isoformat() if r[11] else None,
        }
        for r in rows
    ]


# ---- Upgrade helpers: journey, schema evolution, replay audit reads ----


def log_event_journey(
    event_id: Optional[str],
    payload: Optional[Dict[str, Any]],
    stage: str,
    component: str,
    status: str,
    reason: Optional[str] = None,
    action: Optional[str] = None,
    risk_level: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Append one row to the event journey trace. Fail closed because tracing must not break ingestion."""
    try:
        event_hash = payload_fingerprint(payload or {}) if payload else None
        query = """
        INSERT INTO event_journey(event_id, event_hash, stage, component, status, reason, action, risk_level, payload, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    (
                        event_id,
                        event_hash,
                        stage,
                        component,
                        status,
                        reason,
                        action,
                        risk_level,
                        json.dumps(payload or {}),
                        json.dumps(metadata or {}),
                    ),
                )
    except Exception as exc:
        print(f"event_journey logging skipped: {exc}")


def list_event_journey(limit: int = 200, event_id: Optional[str] = None):
    limit = max(1, min(int(limit), 1000))
    params: list[Any] = []
    where = ""
    if event_id:
        where = "WHERE event_id = %s"
        params.append(event_id)
    query = f"""
    SELECT journey_id, event_id, stage, component, status, reason, action, risk_level, payload, metadata, created_at
    FROM event_journey
    {where}
    ORDER BY created_at DESC, journey_id DESC
    LIMIT %s;
    """
    params.append(limit)
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
    return [
        {
            "journey_id": r[0],
            "event_id": r[1],
            "stage": r[2],
            "component": r[3],
            "status": r[4],
            "reason": r[5],
            "action": r[6],
            "risk_level": r[7],
            "payload": r[8],
            "metadata": r[9],
            "created_at": r[10].isoformat() if r[10] else None,
        }
        for r in rows
    ]


def list_schema_versions():
    query = """
    SELECT schema_version, schema_name, compatibility, description, example_payload, is_supported, created_at
    FROM schema_versions
    ORDER BY schema_version;
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
    return [
        {
            "schema_version": r[0],
            "schema_name": r[1],
            "compatibility": r[2],
            "description": r[3],
            "example_payload": r[4],
            "is_supported": r[5],
            "created_at": r[6].isoformat() if r[6] else None,
        }
        for r in rows
    ]


def list_replay_audit(limit: int = 100):
    limit = max(1, min(int(limit), 500))
    query = """
    SELECT replay_id, event_id, original_payload, replayed_payload, replay_status, reviewer, reviewer_notes, failure_reason, created_at
    FROM dlq_replay_audit
    ORDER BY created_at DESC
    LIMIT %s;
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (limit,))
            rows = cur.fetchall()
    return [
        {
            "replay_id": r[0],
            "event_id": r[1],
            "original_payload": r[2],
            "replayed_payload": r[3],
            "replay_status": r[4],
            "reviewer": r[5],
            "reviewer_notes": r[6],
            "failure_reason": r[7],
            "created_at": r[8].isoformat() if r[8] else None,
        }
        for r in rows
    ]
