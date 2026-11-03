"""Service functions for the Streamlit monitoring dashboard.

The dashboard intentionally calls MCP-compatible tools for pipeline operations
and PostgreSQL for read-heavy dashboard queries. Keeping this logic out of
Streamlit makes it easy to test.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def get_db_connection():
    from src.db import get_db_connection as _get_db_connection

    return _get_db_connection()


def call_pipeline_tool(tool_name: str, **arguments: Any) -> Any:
    from src.mcp_layer.tool_client import call_pipeline_tool as _call_pipeline_tool

    return _call_pipeline_tool(tool_name, **arguments)


def get_pipeline_summary() -> Dict[str, Any]:
    """Return high level pipeline counts for the dashboard cards."""
    query = """
    SELECT
        (SELECT COUNT(*) FROM orders) AS orders_count,
        (SELECT COUNT(*) FROM pipeline_incidents) AS incident_count,
        (SELECT COUNT(*) FROM pipeline_incidents WHERE status = 'healed') AS healed_count,
        (SELECT COUNT(*) FROM pipeline_incidents WHERE status = 'manual_review') AS manual_review_count,
        (SELECT COUNT(*) FROM pipeline_incidents WHERE status = 'failed') AS failed_count,
        (SELECT COUNT(*) FROM pipeline_incidents WHERE status IN ('failed', 'manual_review')) AS unresolved_count;
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            row = cur.fetchone()

    dlq = call_pipeline_tool("get_dlq_count")
    dlq_count = int((dlq or {}).get("message_count", 0))

    orders_count = int(row[0])
    incident_count = int(row[1])
    healed_count = int(row[2])
    manual_review_count = int(row[3])
    failed_count = int(row[4])
    total_seen = orders_count + incident_count
    return {
        "orders_count": orders_count,
        "incident_count": incident_count,
        "healed_count": healed_count,
        "manual_review_count": manual_review_count,
        "failed_count": failed_count,
        "unresolved_count": int(row[5]),
        "dlq_count": dlq_count,
        "total_seen": total_seen,
        "healing_rate": (
            round(healed_count / incident_count, 4) if incident_count else 0
        ),
        "clean_insert_rate": round(orders_count / total_seen, 4) if total_seen else 0,
        "risk_score": min(
            100, failed_count * 10 + manual_review_count * 6 + dlq_count * 8
        ),
    }


def list_incidents(
    limit: int = 50, status: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Return incidents ordered by newest first."""
    limit = max(1, min(int(limit), 200))
    params: list[Any] = []
    where = ""
    if status and status != "all":
        where = "WHERE status = %s"
        params.append(status)

    query = f"""
    SELECT incident_id, event_id, error_type, error_message, original_payload,
           healed_payload, healing_action, risk_level, status, created_at, agent_trace, rag_evidence
    FROM pipeline_incidents
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
            "incident_id": row[0],
            "event_id": row[1],
            "error_type": row[2],
            "error_message": row[3],
            "original_payload": row[4],
            "healed_payload": row[5],
            "healing_action": row[6],
            "risk_level": row[7],
            "status": row[8],
            "created_at": row[9].isoformat() if row[9] else None,
            "agent_trace": row[10] if len(row) > 10 else [],
            "rag_evidence": row[11] if len(row) > 11 else [],
        }
        for row in rows
    ]


def list_reconciliation_runs(limit: int = 20) -> List[Dict[str, Any]]:
    """Return recent Airflow or manual reconciliation runs."""
    limit = max(1, min(int(limit), 100))
    query = """
    SELECT run_id, run_date, orders_count, incident_count, dlq_count,
           unresolved_incident_count, notes, created_at
    FROM reconciliation_runs
    ORDER BY created_at DESC
    LIMIT %s;
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (limit,))
            rows = cur.fetchall()

    return [
        {
            "run_id": row[0],
            "run_date": row[1].isoformat() if row[1] else None,
            "orders_count": row[2],
            "incident_count": row[3],
            "dlq_count": row[4],
            "unresolved_incident_count": row[5],
            "notes": row[6],
            "created_at": row[7].isoformat() if row[7] else None,
        }
        for row in rows
    ]


def update_incident_status(
    incident_id: int, status: str, reviewer_notes: str = ""
) -> Dict[str, Any]:
    """Approve, reject, or close an incident from the dashboard.

    The current schema does not have a separate reviewer_notes column, so notes
    are appended to the existing error_message to keep the MVP compact.
    """
    allowed = {"healed", "manual_review", "failed", "approved_for_replay", "closed"}
    if status not in allowed:
        raise ValueError(f"Unsupported status: {status}")

    query = """
    UPDATE pipeline_incidents
    SET status = %s,
        error_message = CASE
            WHEN %s = '' THEN error_message
            ELSE error_message || E'\nReviewer note: ' || %s
        END
    WHERE incident_id = %s
    RETURNING incident_id, event_id, status;
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (status, reviewer_notes, reviewer_notes, incident_id))
            row = cur.fetchone()

    if not row:
        return {"updated": False, "incident_id": incident_id}
    return {
        "updated": True,
        "incident_id": row[0],
        "event_id": row[1],
        "status": row[2],
    }


def run_reconciliation_now() -> Dict[str, Any]:
    """Run the Airflow reconciliation logic through the MCP tool layer."""
    return call_pipeline_tool("run_reconciliation")


def peek_dlq(max_messages: int = 5) -> List[Dict[str, Any]]:
    """Return a DLQ sample through the MCP tool layer."""
    return call_pipeline_tool("peek_dlq", max_messages=max_messages)


def replay_payload_to_raw_topic(
    payload: Dict[str, Any], target_topic: str = "raw_orders"
) -> Dict[str, Any]:
    """Replay a reviewed payload back to Kafka through the MCP tool layer."""
    return call_pipeline_tool(
        "replay_dlq_event", payload=payload, target_topic=target_topic
    )


def _redis_client():
    from redis import Redis
    from src.config import REDIS_HOST, REDIS_PORT

    return Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


def get_consumer_state() -> Dict[str, Any]:
    """Return whether the consumer is paused by dashboard/API control."""
    try:
        value = _redis_client().get("consumer:paused")
        return {"paused": value == "true", "source": "redis"}
    except Exception as exc:
        return {"paused": False, "source": "fallback", "error": str(exc)}


def set_consumer_paused(paused: bool) -> Dict[str, Any]:
    """Pause or resume the consumer without stopping the container."""
    try:
        _redis_client().set("consumer:paused", "true" if paused else "false")
        return {"updated": True, "paused": paused}
    except Exception as exc:
        return {"updated": False, "paused": False, "error": str(exc)}


def publish_custom_event(
    payload: Dict[str, Any], transform: bool = False
) -> Dict[str, Any]:
    from src.event_gateway import publish_event

    return publish_event(payload, transform=transform)


def publish_demo_dataset(transform: bool = False) -> Dict[str, Any]:
    from src.event_gateway import publish_demo_events

    return publish_demo_events(transform=transform)


def preview_transformation(payload: Dict[str, Any]) -> Dict[str, Any]:
    from src.transformations import transform_order_payload

    transformed, steps = transform_order_payload(payload)
    return {"original": payload, "transformed": transformed, "steps": steps}


def get_demo_catalog() -> Dict[str, Any]:
    from src.data_catalog import demo_data_description

    return demo_data_description()


def list_orders(limit: int = 50) -> List[Dict[str, Any]]:
    """Return recent clean orders for the dashboard data view."""
    limit = max(1, min(int(limit), 200))
    query = """
    SELECT event_id, event_hash, schema_version, customer_id, amount, currency, status, created_at
    FROM orders
    ORDER BY created_at DESC
    LIMIT %s;
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (limit,))
            rows = cur.fetchall()

    return [
        {
            "event_id": row[0],
            "event_hash": row[1],
            "schema_version": row[2],
            "customer_id": row[3],
            "amount": float(row[4]),
            "currency": row[5],
            "status": row[6],
            "created_at": row[7].isoformat() if row[7] else None,
        }
        for row in rows
    ]


def get_agent_decision_traces(
    limit: int = 25, status: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Return incidents as explainable agent decision traces."""
    traces = list_incidents(limit=limit, status=status)
    for trace in traces:
        action = trace.get("healing_action") or "manual_review_or_dlq"
        trace["agent_steps"] = [
            {"step": "1. Detect", "detail": trace.get("error_message")},
            {
                "step": "2. Retrieve with RAG",
                "detail": "Search vector incident memory for similar failed payloads before deciding.",
            },
            {
                "step": "3. Reason",
                "detail": f"Choose action={action} based on schema error, business risk, similar incidents, and guardrails.",
            },
            {
                "step": "4. Act",
                "detail": f"Apply safe action={action}, route high risk records to human approval, or quarantine in DLQ.",
            },
            {
                "step": "5. Verify",
                "detail": "Validate healed payload again with schema and business rules before inserting into PostgreSQL.",
            },
            {"step": "6. Final routing", "detail": trace.get("status")},
        ]
    return traces


def build_test_event(scenario: str, prefix: str = "ui") -> Dict[str, Any]:
    from src.data_catalog import build_demo_event

    return build_demo_event(scenario=scenario, prefix=prefix)


def publish_test_event(
    scenario: str, transform: bool = False, prefix: str = "ui"
) -> Dict[str, Any]:
    payload = build_test_event(scenario=scenario, prefix=prefix)
    result = publish_custom_event(payload, transform=transform)
    result["scenario"] = scenario
    return result


# ---- Upgrade dashboard/API services ----


def list_event_journey(
    limit: int = 200, event_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    from src.db import list_event_journey as _list_event_journey

    return _list_event_journey(limit=limit, event_id=event_id)


def list_replay_audit(limit: int = 100) -> List[Dict[str, Any]]:
    from src.db import list_replay_audit as _list_replay_audit

    return _list_replay_audit(limit=limit)


def list_schema_versions() -> List[Dict[str, Any]]:
    from src.db import list_schema_versions as _list_schema_versions

    return _list_schema_versions()


def pressure_test_summary() -> Dict[str, Any]:
    query = """
    SELECT
      (SELECT COUNT(*) FROM event_journey WHERE stage='published') AS published,
      (SELECT COUNT(*) FROM event_journey WHERE stage='consumed') AS consumed,
      (SELECT COUNT(*) FROM event_journey WHERE stage='inserted') AS inserted,
      (SELECT COUNT(*) FROM event_journey WHERE stage='agent_healed') AS agent_healed,
      (SELECT COUNT(*) FROM event_journey WHERE stage='human_review') AS human_review,
      (SELECT COUNT(*) FROM event_journey WHERE stage='dlq') AS dlq;
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            r = cur.fetchone()
    return {
        "published": r[0],
        "consumed": r[1],
        "inserted": r[2],
        "agent_healed": r[3],
        "human_review": r[4],
        "dlq": r[5],
    }


def rag_evidence(limit: int = 50) -> List[Dict[str, Any]]:
    rows = list_incidents(limit=limit)
    return [
        {
            "incident_id": r.get("incident_id"),
            "event_id": r.get("event_id"),
            "error_type": r.get("error_type"),
            "rag_evidence": r.get("rag_evidence") or [],
            "agent_action": r.get("healing_action"),
            "status": r.get("status"),
        }
        for r in rows
    ]
