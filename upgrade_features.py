from pathlib import Path
import re, json
root = Path('/mnt/data/upgrade_work')

# 1 db init add columns/tables
init = root/'db/init.sql'
s = init.read_text()
append = r'''

-- Upgrade: live event journey, RAG evidence, schema evolution, and failure simulations.
ALTER TABLE pipeline_incidents ADD COLUMN IF NOT EXISTS agent_trace JSONB;
ALTER TABLE pipeline_incidents ADD COLUMN IF NOT EXISTS rag_evidence JSONB;
ALTER TABLE pipeline_incidents ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

CREATE TABLE IF NOT EXISTS event_journey (
    journey_id SERIAL PRIMARY KEY,
    event_id TEXT,
    event_hash TEXT,
    stage TEXT NOT NULL,
    component TEXT NOT NULL,
    status TEXT NOT NULL,
    reason TEXT,
    action TEXT,
    risk_level TEXT,
    payload JSONB,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS schema_versions (
    schema_version INTEGER PRIMARY KEY,
    schema_name TEXT NOT NULL,
    compatibility TEXT NOT NULL DEFAULT 'backward',
    description TEXT,
    example_payload JSONB,
    is_supported BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO schema_versions(schema_version, schema_name, compatibility, description, example_payload, is_supported)
VALUES
(1, 'order_v1', 'baseline', 'Baseline order schema with amount as dollars and status enum.', '{"event_id":"evt_1","customer_id":"cust_1","amount":49.99,"currency":"USD","status":"paid","schema_version":1}', TRUE),
(2, 'order_v2', 'backward', 'Schema v2 accepts amount_cents and order_state, then normalizes to v1 contract for the sink.', '{"event_id":"evt_2","customer_id":"cust_1","amount_cents":4999,"currency":"USD","order_state":"PAID","schema_version":2}', TRUE)
ON CONFLICT (schema_version) DO NOTHING;
'''
if 'CREATE TABLE IF NOT EXISTS event_journey' not in s:
    init.write_text(s + append)

# 2 db.py append/modify insert_incident signature and insert values
p = root/'src/db.py'
s = p.read_text()
# replace insert_incident signature and query to add agent_trace/rag_evidence
old = '''def insert_incident(
    original_payload: Dict[str, Any],
    error_type: str,
    error_message: str,
    healed_payload: Optional[Dict[str, Any]] = None,
    healing_action: Optional[str] = None,
    risk_level: Optional[str] = None,
    status: str = "failed",
    confidence: Optional[float] = None,
) -> int:
    query = """
    INSERT INTO pipeline_incidents(
        event_id, event_hash, error_type, error_message, original_payload,
        healed_payload, healing_action, risk_level, confidence, status
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                ),
            )
            return cur.fetchone()[0]
'''
new = '''def insert_incident(
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
'''
if old in s:
    s = s.replace(old,new)
else:
    print('insert_incident old not found')
append = r'''

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
                cur.execute(query, (
                    event_id, event_hash, stage, component, status, reason, action, risk_level,
                    json.dumps(payload or {}), json.dumps(metadata or {})
                ))
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
    return [{
        "journey_id": r[0], "event_id": r[1], "stage": r[2], "component": r[3], "status": r[4],
        "reason": r[5], "action": r[6], "risk_level": r[7], "payload": r[8], "metadata": r[9],
        "created_at": r[10].isoformat() if r[10] else None,
    } for r in rows]


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
    return [{
        "schema_version": r[0], "schema_name": r[1], "compatibility": r[2], "description": r[3],
        "example_payload": r[4], "is_supported": r[5], "created_at": r[6].isoformat() if r[6] else None,
    } for r in rows]


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
    return [{
        "replay_id": r[0], "event_id": r[1], "original_payload": r[2], "replayed_payload": r[3],
        "replay_status": r[4], "reviewer": r[5], "reviewer_notes": r[6], "failure_reason": r[7],
        "created_at": r[8].isoformat() if r[8] else None,
    } for r in rows]
'''
if 'def log_event_journey(' not in s:
    s += append
p.write_text(s)

# 3 schema_registry.py replace
(root/'src/schema_registry.py').write_text(r'''from __future__ import annotations

from typing import Any, Dict, Tuple
from pydantic import ValidationError
from src.schemas import OrderEvent

SUPPORTED_SCHEMA_VERSIONS = {1, 2}

STATUS_MAP = {
    "pay": "paid", "paid": "paid", "paid ": "paid", "created": "created", "create": "created",
    "cancel": "cancelled", "cancelled": "cancelled", "refund": "refunded", "refunded": "refunded",
}


def normalize_schema(payload: Dict[str, Any]) -> tuple[Dict[str, Any], list[str]]:
    """Normalize supported schema versions into the sink contract used by OrderEvent.

    v1: event_id, customer_id, amount, currency, status, schema_version
    v2: event_id, customer_id, amount_cents, currency, order_state, schema_version
    """
    normalized = dict(payload)
    steps: list[str] = []
    version = int(normalized.get("schema_version", 1))
    if version == 2:
        if "amount" not in normalized and "amount_cents" in normalized:
            normalized["amount"] = float(normalized["amount_cents"]) / 100.0
            steps.append("schema_v2.amount_cents_to_amount")
        if "status" not in normalized and "order_state" in normalized:
            normalized["status"] = STATUS_MAP.get(str(normalized["order_state"]).lower().strip(), str(normalized["order_state"]).lower().strip())
            steps.append("schema_v2.order_state_to_status")
        normalized.pop("amount_cents", None)
        normalized.pop("order_state", None)
        # Store normalized records in sink contract while preserving incoming version.
        normalized["schema_version"] = 1
    return normalized, steps


def validate_schema_version(payload: Dict[str, Any]) -> Tuple[bool, str]:
    try:
        version = int(payload.get("schema_version", 1))
    except Exception:
        return False, "schema_version must be an integer"
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        return False, f"Unsupported schema_version={version}. Supported versions={sorted(SUPPORTED_SCHEMA_VERSIONS)}"
    return True, "ok"


def validate_order_event(payload: Dict[str, Any]) -> OrderEvent:
    ok, message = validate_schema_version(payload)
    if not ok:
        raise ValueError(message)
    normalized, _ = normalize_schema(payload)
    return OrderEvent(**normalized)


def explain_validation_error(payload: Dict[str, Any], exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        return str(exc)
    return f"Schema validation failed: {exc}"
''')

# 4 data_catalog add v2 scenario and pressure distribution maybe
p = root/'src/data_catalog.py'
s = p.read_text()
s = s.replace('"missing_event_id",\n]', '"missing_event_id",\n    "schema_v2_order",\n    "unsupported_schema",\n]')
s = s.replace('    if scenario == "missing_event_id":\n        return {"customer_id": "cust_missing_event", "amount": 55.25, "currency": "USD", "status": "paid", "schema_version": 1}\n', '    if scenario == "missing_event_id":\n        return {"customer_id": "cust_missing_event", "amount": 55.25, "currency": "USD", "status": "paid", "schema_version": 1}\n    if scenario == "schema_v2_order":\n        return {"event_id": event_id, "customer_id": "cust_v2", "amount_cents": 4999, "currency": "USD", "order_state": "PAID", "schema_version": 2}\n    if scenario == "unsupported_schema":\n        return {"event_id": event_id, "customer_id": "cust_bad_schema", "amount": 12.0, "currency": "USD", "status": "paid", "schema_version": 99}\n')
s = s.replace('        build_demo_event("missing_event_id", prefix=prefix),\n    ]', '        build_demo_event("missing_event_id", prefix=prefix),\n        build_demo_event("schema_v2_order", prefix=prefix),\n        build_demo_event("unsupported_schema", prefix=prefix),\n    ]')
s = s.replace('+ ["missing_event_id"] * 5\n', '+ ["missing_event_id"] * 5\n        + ["schema_v2_order"] * 8\n        + ["unsupported_schema"] * 2\n')
p.write_text(s)

# 5 event_gateway log publish
p = root/'src/event_gateway.py'
s = p.read_text()
s = s.replace('from src.transformations import transform_order_payload\n', 'from src.transformations import transform_order_payload\nfrom src.db import log_event_journey\n')
s = s.replace('    producer.flush()\n    return {"published": True, "topic": topic, "event_id": event_payload.get("event_id"), "payload": event_payload, "transformation_steps": steps}\n', '    producer.flush()\n    log_event_journey(event_payload.get("event_id"), event_payload, "published", "producer_api", "success", "Event published to Kafka", "produce", metadata={"topic": topic, "transformation_steps": steps})\n    return {"published": True, "topic": topic, "event_id": event_payload.get("event_id"), "payload": event_payload, "transformation_steps": steps}\n')
p.write_text(s)

# 6 consumer log journey, pass trace/evidence
p = root/'src/consumer.py'
s = p.read_text()
s = s.replace('from src.db import insert_order, insert_incident, IdempotencyConflictError\n', 'from src.db import insert_order, insert_incident, IdempotencyConflictError, log_event_journey\n')
s = s.replace('def send_to_dlq(payload: Dict[str, Any], error_message: str):\n    dlq_record = {"payload": payload, "error_message": error_message}\n', 'def send_to_dlq(payload: Dict[str, Any], error_message: str):\n    dlq_record = {"payload": payload, "error_message": error_message}\n    log_event_journey(payload.get("event_id"), payload, "dlq", "kafka_dlq", "quarantined", error_message, "send_to_dlq", risk_level="high", metadata={"topic": DLQ_TOPIC})\n')
s = s.replace('    confidence: float | None = None,\n) -> None:\n    incident_id = insert_incident(\n        payload,\n        error_type,\n        error_message,\n        healed_payload,\n        action,\n        risk_level,\n        status,\n        confidence,\n    )', '    confidence: float | None = None,\n    agent_trace: list[Dict[str, Any]] | None = None,\n    rag_evidence: list[Dict[str, Any]] | None = None,\n) -> None:\n    incident_id = insert_incident(\n        payload,\n        error_type,\n        error_message,\n        healed_payload,\n        action,\n        risk_level,\n        status,\n        confidence,\n        agent_trace=agent_trace,\n        rag_evidence=rag_evidence,\n    )')
s = s.replace('def process_payload(payload: Dict[str, Any]):\n    EVENTS_PROCESSED.inc()', 'def process_payload(payload: Dict[str, Any]):\n    EVENTS_PROCESSED.inc()\n    log_event_journey(payload.get("event_id"), payload, "consumed", "consumer", "success", "Consumer received Kafka message", "consume")')
s = s.replace('        order = validate_order_event(payload)\n        insert_order(order)\n        EVENTS_VALID.inc()\n        print(f"Inserted or skipped valid order: {order.event_id}")', '        order = validate_order_event(payload)\n        log_event_journey(order.event_id, payload, "validated", "schema_registry", "success", "Payload passed schema validation", "validate")\n        insert_order(order)\n        log_event_journey(order.event_id, order.model_dump(), "inserted", "postgres", "success", "Clean record inserted or safely skipped", "insert_order")\n        EVENTS_VALID.inc()\n        print(f"Inserted or skipped valid order: {order.event_id}")')
s = s.replace('        send_to_dlq(payload, str(exc))\n        record_incident_and_memory(payload, "idempotency_conflict", str(exc), None, "send_to_dlq", "high", "failed", 1.0)', '        send_to_dlq(payload, str(exc))\n        log_event_journey(payload.get("event_id"), payload, "idempotency_conflict", "postgres", "failed", str(exc), "send_to_dlq", risk_level="high")\n        record_incident_and_memory(payload, "idempotency_conflict", str(exc), None, "send_to_dlq", "high", "failed", 1.0)')
s = s.replace('        print(f"Validation failed. Starting self healing graph. Error: {error_message}")', '        log_event_journey(payload.get("event_id"), payload, "validation_failed", "schema_registry", "failed", error_message, "start_agent")\n        print(f"Validation failed. Starting self healing graph. Error: {error_message}")')
s = s.replace('        decision = result.get("decision") or {}', '        decision = result.get("decision") or {}\n        agent_trace = result.get("agent_trace") or []\n        rag_evidence = result.get("similar_incidents") or []\n        log_event_journey(payload.get("event_id"), payload, "agent_decision", "langgraph_agent", final_status, decision.get("reason"), action=decision.get("action"), risk_level=decision.get("risk_level"), metadata={"agent_trace": agent_trace, "rag_evidence": rag_evidence})')
s = s.replace('                record_incident_and_memory(payload, "validation_error", error_message, healed_payload, action, risk_level, "healed", confidence)', '                log_event_journey(healed_order.event_id, healed_payload, "agent_healed", "langgraph_agent", "success", "Reason Act Verify passed and healed record was inserted", action, risk_level, metadata={"agent_trace": agent_trace})\n                record_incident_and_memory(payload, "validation_error", error_message, healed_payload, action, risk_level, "healed", confidence, agent_trace, rag_evidence)')
s = s.replace('                record_incident_and_memory(payload, "post_healing_insert_failure", str(insert_exc), healed_payload, action, "high", "failed", confidence)', '                record_incident_and_memory(payload, "post_healing_insert_failure", str(insert_exc), healed_payload, action, "high", "failed", confidence, agent_trace, rag_evidence)')
s = s.replace('            record_incident_and_memory(payload, "validation_error", error_message, healed_payload, action, risk_level, "manual_review", confidence)', '            log_event_journey(payload.get("event_id"), payload, "human_review", "approval_queue", "pending", "Risk gate requires human approval", action, risk_level, metadata={"agent_trace": agent_trace})\n            record_incident_and_memory(payload, "validation_error", error_message, healed_payload, action, risk_level, "manual_review", confidence, agent_trace, rag_evidence)')
s = s.replace('            record_incident_and_memory(payload, "validation_error", error_message, healed_payload, action, risk_level, "failed", confidence)', '            record_incident_and_memory(payload, "validation_error", error_message, healed_payload, action, risk_level, "failed", confidence, agent_trace, rag_evidence)')
p.write_text(s)

# 7 dashboard_service append upgrade functions and modify list_incidents query to include cols if can
p = root/'src/dashboard_service.py'
s = p.read_text()
s = s.replace('healed_payload, healing_action, risk_level, status, created_at\n', 'healed_payload, healing_action, risk_level, status, created_at, agent_trace, rag_evidence\n')
s = s.replace('            "created_at": row[9].isoformat() if row[9] else None,\n', '            "created_at": row[9].isoformat() if row[9] else None,\n            "agent_trace": row[10] if len(row) > 10 else [],\n            "rag_evidence": row[11] if len(row) > 11 else [],\n')
append = r'''

# ---- Upgrade dashboard/API services ----

def list_event_journey(limit: int = 200, event_id: Optional[str] = None) -> List[Dict[str, Any]]:
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
    return {"published": r[0], "consumed": r[1], "inserted": r[2], "agent_healed": r[3], "human_review": r[4], "dlq": r[5]}


def rag_evidence(limit: int = 50) -> List[Dict[str, Any]]:
    rows = list_incidents(limit=limit)
    return [{
        "incident_id": r.get("incident_id"),
        "event_id": r.get("event_id"),
        "error_type": r.get("error_type"),
        "rag_evidence": r.get("rag_evidence") or [],
        "agent_action": r.get("healing_action"),
        "status": r.get("status"),
    } for r in rows]
'''
if 'def pressure_test_summary' not in s:
    s += append
p.write_text(s)

# 8 failure_simulator.py
(root/'src/failure_simulator.py').write_text(r'''from __future__ import annotations

from typing import Any, Dict
from confluent_kafka.admin import AdminClient, NewTopic
from src.config import KAFKA_BOOTSTRAP_SERVERS, DLQ_TOPIC, RAW_TOPIC, REDIS_HOST, REDIS_PORT
from src.dashboard_service import set_consumer_paused
from src.event_gateway import publish_event
from src.data_catalog import build_demo_event
from src.db import insert_pipeline_step_incident, update_pipeline_step_incident

SCENARIOS = [
    {"id": "missing_dlq_topic", "label": "Delete DLQ topic", "risk": "medium", "description": "Deletes dead_letter_events so pipeline step healing can recreate it."},
    {"id": "pause_consumer", "label": "Pause consumer", "risk": "low", "description": "Sets Redis pause flag so consumer stops processing until healed."},
    {"id": "openai_unavailable", "label": "Simulate OpenAI unavailable", "risk": "low", "description": "Enables deterministic fallback flag so the system demonstrates degraded LLM mode."},
    {"id": "unsupported_schema_event", "label": "Publish unsupported schema", "risk": "medium", "description": "Sends schema_version 99 event to demonstrate schema evolution handling."},
    {"id": "transformation_exception", "label": "Publish transformation exception candidate", "risk": "low", "description": "Sends malformed amount to show manual review or DLQ."},
]


def scenarios() -> Dict[str, Any]:
    return {"scenarios": SCENARIOS}


def run_failure_simulation(scenario: str) -> Dict[str, Any]:
    admin = AdminClient({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})
    if scenario == "missing_dlq_topic":
        fs = admin.delete_topics([DLQ_TOPIC], operation_timeout=10)
        result = {}
        for topic, fut in fs.items():
            try:
                fut.result(timeout=10)
                result[topic] = "deleted"
            except Exception as exc:
                result[topic] = f"delete_attempt: {exc}"
        incident_id = insert_pipeline_step_incident("kafka", "missing_topic_simulation", "Failure simulator deleted or attempted to delete DLQ topic.", {"topic": DLQ_TOPIC}, "create_missing_topic", risk_level="medium", status="simulated")
        return {"scenario": scenario, "result": result, "step_incident_id": incident_id}
    if scenario == "pause_consumer":
        set_consumer_paused(True)
        incident_id = insert_pipeline_step_incident("consumer", "paused_by_simulator", "Failure simulator paused the consumer.", {"consumer_paused": True}, "resume_consumer", risk_level="low", status="simulated")
        return {"scenario": scenario, "paused": True, "step_incident_id": incident_id}
    if scenario == "openai_unavailable":
        import redis
        redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True).set("llm:fallback_mode", "deterministic")
        incident_id = insert_pipeline_step_incident("openai", "simulated_unavailable", "Failure simulator enabled deterministic fallback mode.", {"fallback_mode": "deterministic"}, "enable_deterministic_fallback", risk_level="low", status="simulated")
        return {"scenario": scenario, "fallback_mode": "deterministic", "step_incident_id": incident_id}
    if scenario == "unsupported_schema_event":
        payload = build_demo_event("unsupported_schema", prefix="failure_sim")
        return {"scenario": scenario, "publish_result": publish_event(payload)}
    if scenario == "transformation_exception":
        payload = build_demo_event("valid_order", prefix="failure_sim")
        payload["amount"] = "$not-a-number"
        return {"scenario": scenario, "publish_result": publish_event(payload)}
    raise ValueError(f"Unsupported failure simulation: {scenario}")
''')

# 9 api add imports/classes/endpoints
p = root/'src/api/app.py'
s = p.read_text()
s = s.replace('from src.pipeline_health import get_pipeline_health, heal_safe_pipeline_steps, heal_pipeline_component, recent_pipeline_step_incidents\n', 'from src.pipeline_health import get_pipeline_health, heal_safe_pipeline_steps, heal_pipeline_component, recent_pipeline_step_incidents\nfrom src.failure_simulator import scenarios as failure_scenarios, run_failure_simulation\nfrom src.dashboard_service import list_event_journey, list_replay_audit, list_schema_versions, pressure_test_summary, rag_evidence\n')
s = s.replace('class PipelineHealRequest(BaseModel):\n    component: str\n    action: str | None = None\n    approve_risky: bool = False\n', 'class PipelineHealRequest(BaseModel):\n    component: str\n    action: str | None = None\n    approve_risky: bool = False\n\n\nclass FailureSimulationRequest(BaseModel):\n    scenario: str\n')
append = r'''

@app.get("/failure-simulator/scenarios")
def get_failure_scenarios() -> Dict[str, Any]:
    return failure_scenarios()


@app.post("/failure-simulator/run")
def run_failure(request: FailureSimulationRequest) -> Dict[str, Any]:
    return run_failure_simulation(request.scenario)


@app.get("/event-journey")
def event_journey(limit: int = Query(default=200, ge=1, le=1000), event_id: str | None = None) -> List[Dict[str, Any]]:
    return list_event_journey(limit=limit, event_id=event_id)


@app.get("/dlq/replay-audit")
def replay_audit(limit: int = Query(default=100, ge=1, le=500)) -> List[Dict[str, Any]]:
    return list_replay_audit(limit=limit)


@app.get("/schema/evolution")
def schema_evolution() -> Dict[str, Any]:
    return {
        "supported_versions": list_schema_versions(),
        "policy": "v2 payloads are normalized to the v1 sink contract. Unsupported versions route through Reason -> Act -> Verify and usually go to manual review or DLQ.",
        "examples": {
            "v1": {"event_id":"evt_1","customer_id":"cust_1","amount":49.99,"currency":"USD","status":"paid","schema_version":1},
            "v2": {"event_id":"evt_2","customer_id":"cust_1","amount_cents":4999,"currency":"USD","order_state":"PAID","schema_version":2},
        }
    }


@app.get("/pressure-test/summary")
def pressure_summary() -> Dict[str, Any]:
    return pressure_test_summary()


@app.get("/rag/evidence")
def get_rag_evidence(limit: int = Query(default=50, ge=1, le=200)) -> List[Dict[str, Any]]:
    return rag_evidence(limit=limit)
'''
if '/failure-simulator/scenarios' not in s:
    s += append
p.write_text(s)

# 10 docker-compose add env OPENAI to data-api/consumer and ENABLE_LLM fallback
p = root/'docker-compose.yml'
s = p.read_text()
s = s.replace('      MCP_CLIENT_MODE: local\n    ports:\n      - "8000:8000"', '      MCP_CLIENT_MODE: local\n      OPENAI_API_KEY: ${OPENAI_API_KEY:-}\n      ENABLE_LLM: ${ENABLE_LLM:-true}\n    ports:\n      - "8000:8000"')
s = s.replace('      MCP_CLIENT_MODE: local\n      ENABLE_PROMETHEUS_SERVER: "true"', '      MCP_CLIENT_MODE: local\n      OPENAI_API_KEY: ${OPENAI_API_KEY:-}\n      ENABLE_LLM: ${ENABLE_LLM:-true}\n      ENABLE_PROMETHEUS_SERVER: "true"')
p.write_text(s)

# 11 frontend replace main.tsx with modern dashboard
(root/'frontend/src/main.tsx').write_text(r'''import React, {useEffect, useMemo, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {Activity, AlertTriangle, Bot, CheckCircle, Database, GitBranch, Pause, Play, RefreshCw, Send, ServerCog, ShieldCheck, Workflow, XCircle, Zap, Eye, RotateCcw, Gauge} from 'lucide-react';
import {BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line, CartesianGrid, AreaChart, Area} from 'recharts';
import {API_BASE, apiGet, apiPost} from './lib/api';
import './styles.css';

type AnyObj = Record<string, any>;
type Summary = {orders_count:number; incident_count:number; healed_count:number; manual_review_count:number; failed_count:number; unresolved_count:number; dlq_count:number; total_seen?:number; healing_rate?:number; clean_insert_rate?:number; risk_score?:number;};
type Incident = {incident_id:number; event_id?:string; error_type:string; error_message:string; original_payload:any; healed_payload?:any; healing_action?:string; risk_level?:string; status:string; created_at?:string; agent_trace?:AnyObj[]; rag_evidence?:AnyObj[];};
type Order = {event_id:string; customer_id:string; amount:number; currency:string; status:string; schema_version?:number; created_at:string;};
type Journey = {journey_id:number; event_id?:string; stage:string; component:string; status:string; reason?:string; action?:string; risk_level?:string; payload?:any; metadata?:any; created_at?:string;};
type ComponentHealth = {component:string; status:string; problem_type?:string; reason?:string; detected_state?:any; risk_level?:string; suggested_action?:string; requires_human_approval?:boolean;};

const tabs = ['Overview','System Design','Failure Simulator','Live Journey','Reason Act Verify','Producer Controls','Pressure Test','PostgreSQL Records','Human Approval','DLQ Replay','RAG Evidence','Schema Evolution','Pipeline Step Healing','Metrics'];
const scenarios = ['valid_order','amount_string','missing_currency','bad_status','negative_amount','missing_customer','missing_event_id','schema_v2_order','unsupported_schema'];
const COLORS = ['#22c55e','#38bdf8','#f59e0b','#ef4444','#a78bfa','#ec4899'];

function JsonBlock({data}:{data:any}) { return <pre className="json-block">{JSON.stringify(data, null, 2)}</pre>; }
function Stat({title,value,icon,color}:{title:string;value:any;icon:React.ReactNode;color?:string}) { return <div className={`stat-card ${color||''}`}><div className="stat-icon">{icon}</div><div><div className="stat-title">{title}</div><div className="stat-value">{value ?? 0}</div></div></div>; }

function App() {
  const [tab,setTab] = useState('Overview');
  const [summary,setSummary] = useState<Summary|null>(null);
  const [orders,setOrders] = useState<Order[]>([]);
  const [incidents,setIncidents] = useState<Incident[]>([]);
  const [journey,setJourney] = useState<Journey[]>([]);
  const [health,setHealth] = useState<any>(null);
  const [pipelineIncidents,setPipelineIncidents] = useState<any[]>([]);
  const [flow,setFlow] = useState<any>(null);
  const [replayAudit,setReplayAudit] = useState<any[]>([]);
  const [schema,setSchema] = useState<any>(null);
  const [rag,setRag] = useState<any[]>([]);
  const [pressure,setPressure] = useState<any>(null);
  const [failureScenarios,setFailureScenarios] = useState<any[]>([]);
  const [message,setMessage] = useState('');
  const [error,setError] = useState('');
  const [customJson,setCustomJson] = useState(JSON.stringify({event_id:'ui_custom_1',customer_id:'cust_ui',amount:'42.50',currency:'usd',status:'PAY',schema_version:1}, null, 2));
  const [transformResult,setTransformResult] = useState<any>(null);
  const [pressureTotal,setPressureTotal] = useState(1000);

  async function refresh() {
    try {
      setError('');
      const [s,o,i,j,h,pi,f,ra,sc,rg,ps,fs] = await Promise.all([
        apiGet<Summary>('/summary'), apiGet<Order[]>('/orders?limit=100'), apiGet<Incident[]>('/incidents?limit=100'),
        apiGet<Journey[]>('/event-journey?limit=300'), apiGet<any>('/pipeline/health'), apiGet<any[]>('/pipeline/incidents?limit=100'),
        apiGet<any>('/flow/live'), apiGet<any[]>('/dlq/replay-audit?limit=100'), apiGet<any>('/schema/evolution'), apiGet<any[]>('/rag/evidence?limit=100'),
        apiGet<any>('/pressure-test/summary'), apiGet<any>('/failure-simulator/scenarios')
      ]);
      setSummary(s); setOrders(o); setIncidents(i); setJourney(j); setHealth(h); setPipelineIncidents(pi); setFlow(f); setReplayAudit(ra); setSchema(sc); setRag(rg); setPressure(ps); setFailureScenarios(fs.scenarios || []);
    } catch(e:any) { setError(e.message || String(e)); }
  }
  useEffect(()=>{ refresh(); const t=setInterval(refresh, 6000); return ()=>clearInterval(t); },[]);

  async function publishDemo(){ const r=await apiPost('/events/demo'); setMessage(`Published ${r.published_count} demo events`); setTimeout(refresh,1000); }
  async function publishScenario(sc:string){ const r=await apiPost(`/events/test/${sc}`); setMessage(`Published ${sc}: ${r.event_id || r?.payload?.event_id || ''}`); setTimeout(refresh,1000); }
  async function publishCustom(){ const payload=JSON.parse(customJson); const r=await apiPost('/events',{payload}); setMessage(`Published custom event ${r.event_id}`); setTimeout(refresh,1000); }
  async function previewTransform(){ const payload=JSON.parse(customJson); setTransformResult(await apiPost('/transform',{payload})); }
  async function pause(paused:boolean){ const r=await apiPost('/consumer/state',{paused}); setMessage(paused?'Consumer paused':'Consumer resumed'); setTimeout(refresh,500); }
  async function pressureRun(){ const r=await apiPost(`/events/pressure-test?total=${pressureTotal}`); setMessage(`Pressure test published ${r.published_count} events`); setTimeout(refresh,1500); }
  async function runFailure(sc:string){ const r=await apiPost('/failure-simulator/run',{scenario:sc}); setMessage(`Simulated ${sc}`); setTimeout(refresh,1000); }
  async function healSafe(){ const r=await apiPost('/pipeline/heal/safe'); setMessage('Safe pipeline healing executed'); setTimeout(refresh,1000); }
  async function approveIncident(id:number,status:string){ const r=await apiPost(`/incidents/${id}/status`,{status, reviewer_notes:'Reviewed from dashboard'}); setMessage(`Incident ${id} -> ${status}`); setTimeout(refresh,1000); }
  async function replayPayload(payload:any){ const r=await apiPost('/dlq/replay',{payload, reviewer:'dashboard', reviewer_notes:'replayed from DLQ tab'}); setMessage(`Replay submitted`); setTimeout(refresh,1000); }

  const chartData = useMemo(()=> summary ? [
    {name:'Orders', value:summary.orders_count}, {name:'Healed', value:summary.healed_count}, {name:'Manual', value:summary.manual_review_count}, {name:'Failed', value:summary.failed_count}, {name:'DLQ', value:summary.dlq_count}
  ] : [], [summary]);
  const timeline = useMemo(()=> [...journey].reverse().slice(-80).map((j,idx)=>({idx, stage:j.stage, count:idx+1})), [journey]);

  return <div className="app-shell"><aside className="sidebar"><div className="brand"><div className="logo">SH</div><div><h1>Self Healing Platform</h1><p>Records + pipeline step healing</p></div></div>{tabs.map(t=><button key={t} className={tab===t?'active':''} onClick={()=>setTab(t)}>{t}</button>)}</aside><main><div className="topbar"><div><h1>{tab}</h1><p>Kafka → Consumer → Transform → Validate → Agent → PostgreSQL / Human / DLQ</p></div><button onClick={refresh}><RefreshCw size={16}/> Refresh</button></div>{error&&<div className="error">{error}</div>}{message&&<div className="toast">{message}</div>}

  {tab==='Overview' && <><div className="cards-grid"><Stat title="Clean Orders" value={summary?.orders_count} icon={<Database/>} color="green"/><Stat title="Incidents" value={summary?.incident_count} icon={<AlertTriangle/>} color="yellow"/><Stat title="Agent Healed" value={summary?.healed_count} icon={<Bot/>} color="blue"/><Stat title="Human Review" value={summary?.manual_review_count} icon={<ShieldCheck/>} color="purple"/><Stat title="Failed" value={summary?.failed_count} icon={<XCircle/>} color="red"/><Stat title="DLQ" value={summary?.dlq_count} icon={<GitBranch/>} color="red"/></div><div className="charts-grid"><div className="chart-card"><h3>Outcome split</h3><ResponsiveContainer width="100%" height={260}><BarChart data={chartData}><XAxis dataKey="name"/><YAxis/><Tooltip/><Bar dataKey="value" fill="#38bdf8"/></BarChart></ResponsiveContainer></div><div className="chart-card"><h3>Risk and healing rates</h3><JsonBlock data={{healing_rate:summary?.healing_rate, clean_insert_rate:summary?.clean_insert_rate, risk_score:summary?.risk_score, pressure_summary:pressure}}/></div></div></>}

  {tab==='System Design' && <Panel icon={<Workflow/>} title="Full system design and data journey" desc="Visual map of the whole data flow and every healing route."><div className="pipeline-wrap">{['Producer/API','Kafka raw_orders','Consumer','Transform','Schema Validate','Reason Act Verify Agent','PostgreSQL Orders'].map((n,i)=><React.Fragment key={n}><div className="pipeline-node"><div className="node-title">{n}</div><div className="node-caption">{i===5?'RAG evidence + OpenAI/fallback + guardrails': i===6?'clean and healed records':'live component of pipeline'}</div></div>{i<6&&<div className="arrow">→</div>}</React.Fragment>)}</div><div className="journey-grid"><div className="journey-card"><h3>Agent branch</h3><p>Invalid records move to RAG retrieval, reasoning, safe action selection, verification, and final routing.</p></div><div className="journey-card"><h3>Human branch</h3><p>High risk cases like financial ambiguity or missing customer identity stay pending for approval.</p></div><div className="journey-card"><h3>DLQ branch</h3><p>Unrecoverable or unsafe records are quarantined for later replay, audit, or rejection.</p></div><div className="journey-card"><h3>Pipeline healing</h3><p>Kafka, Redis, Postgres, OpenAI, Airflow, and consumer health are monitored and safely healed.</p></div></div><JsonBlock data={flow}/></Panel>}

  {tab==='Failure Simulator' && <Panel icon={<Zap/>} title="Failure simulator" desc="Break a component or publish failure data, then run safe healing and verify recovery."><div className="button-row"><button onClick={healSafe}><ShieldCheck size={16}/> Run safe pipeline healing</button></div><div className="scenario-grid">{failureScenarios.map((f:any)=><button className="scenario" key={f.id} onClick={()=>runFailure(f.id)}><b>{f.label}</b><br/><span>{f.risk} risk</span></button>)}</div><JsonBlock data={failureScenarios}/></Panel>}

  {tab==='Live Journey' && <Panel icon={<Activity/>} title="Live event journey trace" desc="Every event is traced across producer, Kafka, consumer, validation, agent, human, DLQ, and PostgreSQL."><div className="chart-card"><ResponsiveContainer width="100%" height={220}><AreaChart data={timeline}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="idx"/><YAxis/><Tooltip/><Area dataKey="count" stroke="#38bdf8" fill="#1d4ed8"/></AreaChart></ResponsiveContainer></div><DataTable rows={journey} cols={['created_at','event_id','stage','component','status','action','risk_level','reason']}/></Panel>}

  {tab==='Reason Act Verify' && <Panel icon={<Bot/>} title="Reason → Act → Verify traces" desc="For each incident, see detection, RAG evidence, decision, action, verification, and final route.">{incidents.slice(0,20).map(i=><div className="trace-card" key={i.incident_id}><h3>{i.event_id || 'unknown'} <span className={`pill ${i.status}`}>{i.status}</span></h3><div className="two-col"><div><b>Problem</b><p>{i.error_message}</p><b>Action</b><p>{i.healing_action || 'none'} | risk: {i.risk_level || 'unknown'}</p></div><div><b>Trace</b><ol>{(i.agent_trace && i.agent_trace.length? i.agent_trace : [{step:'Detect',reason:i.error_message},{step:'Reason',reason:`Selected ${i.healing_action}`},{step:'Verify',reason:i.status}]).map((s:any,idx:number)=><li key={idx}><b>{s.step}</b>: {s.reason || s.detail || s.act}</li>)}</ol></div></div></div>)}</Panel>}

  {tab==='Producer Controls' && <Panel icon={<Send/>} title="Producer, consumer and transformation controls" desc="Publish events, pause/resume the consumer, and preview transformations."><div className="button-row"><button onClick={publishDemo}><Send size={16}/> Publish Demo Dataset</button><button onClick={()=>pause(true)}><Pause size={16}/> Pause Consumer</button><button onClick={()=>pause(false)}><Play size={16}/> Resume Consumer</button><button onClick={previewTransform}><Eye size={16}/> Preview Transform</button><button onClick={publishCustom}><Send size={16}/> Publish Custom JSON</button></div><div className="scenario-grid">{scenarios.map(s=><button className="scenario" key={s} onClick={()=>publishScenario(s)}>{s}</button>)}</div><textarea className="code-input" value={customJson} onChange={e=>setCustomJson(e.target.value)}/>{transformResult&&<JsonBlock data={transformResult}/>}</Panel>}

  {tab==='Pressure Test' && <Panel icon={<Gauge/>} title="Pressure test dashboard" desc="Generate many records with clean, healable, human review, and DLQ routes."><div className="button-row"><input value={pressureTotal} type="number" min={1} max={100000} onChange={e=>setPressureTotal(Number(e.target.value))}/><button onClick={pressureRun}><Zap size={16}/> Start pressure test</button></div><JsonBlock data={pressure}/><p>Suggested demo: publish 1,000 records, watch consumer logs, refresh Live Journey, Risk Metrics, Agent Trace, and PostgreSQL Records.</p></Panel>}

  {tab==='PostgreSQL Records' && <Panel icon={<Database/>} title="Inserted PostgreSQL records" desc="These are clean records inserted into the sink table."><DataTable rows={orders} cols={['created_at','event_id','customer_id','amount','currency','status','schema_version']}/><h3>Demo SQL queries</h3><JsonBlock data={{orders:'SELECT event_id, customer_id, amount, currency, status, created_at FROM orders ORDER BY created_at DESC LIMIT 20;', incidents:'SELECT event_id, healing_action, risk_level, confidence, status FROM pipeline_incidents ORDER BY created_at DESC;', event_journey:'SELECT event_id, stage, component, status, reason FROM event_journey ORDER BY created_at DESC LIMIT 100;'}}/></Panel>}

  {tab==='Human Approval' && <Panel icon={<ShieldCheck/>} title="Human approval queue" desc="Risky records are not repaired automatically. Review, approve for replay, reject, or close.">{incidents.filter(i=>i.status==='manual_review').map(i=><div className="trace-card" key={i.incident_id}><h3>{i.event_id} <span className="pill manual_review">manual review</span></h3><p>{i.error_message}</p><div className="button-row"><button onClick={()=>approveIncident(i.incident_id,'approved_for_replay')}>Approve for replay</button><button onClick={()=>approveIncident(i.incident_id,'failed')}>Reject</button><button onClick={()=>approveIncident(i.incident_id,'closed')}>Close</button>{i.healed_payload&&<button onClick={()=>replayPayload(i.healed_payload)}>Replay healed payload</button>}</div><div className="two-col"><JsonBlock data={i.original_payload}/><JsonBlock data={i.healed_payload || {proposed:'none'}}/></div></div>)}</Panel>}

  {tab==='DLQ Replay' && <Panel icon={<RotateCcw/>} title="DLQ replay workflow" desc="Inspect failed records, replay manually fixed payloads, and audit replay attempts."><div className="two-col"><div><h3>Failed incidents</h3>{incidents.filter(i=>i.status==='failed').slice(0,20).map(i=><div className="trace-card" key={i.incident_id}><b>{i.event_id}</b><p>{i.error_message}</p><button onClick={()=>replayPayload(i.original_payload)}>Replay original</button></div>)}</div><div><h3>Replay audit</h3><DataTable rows={replayAudit} cols={['created_at','event_id','replay_status','reviewer','failure_reason']}/></div></div></Panel>}

  {tab==='RAG Evidence' && <Panel icon={<GitBranch/>} title="RAG evidence visibility" desc="Shows retrieved similar incidents used by the agent before it selects an action.">{rag.map((r:any)=><div className="trace-card" key={r.incident_id}><h3>{r.event_id} → {r.agent_action} <span className={`pill ${r.status}`}>{r.status}</span></h3><JsonBlock data={r.rag_evidence}/></div>)}</Panel>}

  {tab==='Schema Evolution' && <Panel icon={<GitBranch/>} title="Schema evolution" desc="Supported schema contracts and normalization policy."><JsonBlock data={schema}/><div className="button-row"><button onClick={()=>publishScenario('schema_v2_order')}>Publish v2 compatible event</button><button onClick={()=>publishScenario('unsupported_schema')}>Publish unsupported schema</button></div></Panel>}

  {tab==='Pipeline Step Healing' && <Panel icon={<ServerCog/>} title="Pipeline step healing" desc="Health checks, safe actions, human approval, and recovery verification for pipeline components."><div className="cards-grid">{(health?.components||[]).map((c:ComponentHealth)=><Stat key={c.component} title={c.component} value={c.status} icon={c.status==='healthy'?<CheckCircle/>:<AlertTriangle/>} color={c.status==='healthy'?'green':'red'}/>)}</div><div className="button-row"><button onClick={healSafe}>Run safe healing</button></div><DataTable rows={pipelineIncidents} cols={['created_at','component','problem_type','reason','recovery_action','risk_level','status','requires_human_approval']}/></Panel>}

  {tab==='Metrics' && <Panel icon={<Activity/>} title="Metrics and risk visualization" desc="Operational metrics and links to Prometheus."><div className="charts-grid"><div className="chart-card"><ResponsiveContainer width="100%" height={260}><PieChart><Pie data={chartData} dataKey="value" nameKey="name" outerRadius={90} label>{chartData.map((_,idx)=><Cell key={idx} fill={COLORS[idx%COLORS.length]}/>)}</Pie><Tooltip/></PieChart></ResponsiveContainer></div><div className="chart-card"><JsonBlock data={{prometheus:'http://localhost:9090', api_metrics:'http://localhost:9108/metrics', consumer_metrics:'http://localhost:9109/metrics', summary}}/></div></div></Panel>}
  </main></div>;
}

function Panel({icon,title,desc,children}:{icon:React.ReactNode;title:string;desc:string;children:React.ReactNode}){return <div className="panel"><div className="panel-head">{icon}<div><h2>{title}</h2><p>{desc}</p></div></div>{children}</div>}
function DataTable({rows,cols}:{rows:any[];cols:string[]}){return <div className="table-wrap"><table><thead><tr>{cols.map(c=><th key={c}>{c}</th>)}</tr></thead><tbody>{rows.slice(0,200).map((r,idx)=><tr key={idx}>{cols.map(c=><td key={c}>{typeof r[c]==='object'?JSON.stringify(r[c]):String(r[c] ?? '')}</td>)}</tr>)}</tbody></table></div>}

createRoot(document.getElementById('root')!).render(<App/>);
''')

# 12 CSS additions
p = root/'frontend/src/styles.css'
s = p.read_text()
extra = r'''
.table-wrap { overflow: auto; border: 1px solid rgba(148,163,184,0.16); border-radius: 16px; margin-top: 14px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { padding: 11px 12px; border-bottom: 1px solid rgba(148,163,184,0.12); text-align: left; vertical-align: top; }
th { background: rgba(15,23,42,0.92); color: #bfdbfe; position: sticky; top: 0; }
td { color: #dbeafe; max-width: 360px; }
.trace-card { background: rgba(2, 6, 23, 0.42); border: 1px solid rgba(148, 163, 184, 0.13); border-radius: 18px; padding: 16px; margin-bottom: 14px; }
.trace-card h3 { margin: 0 0 8px; }
.pill { display: inline-block; padding: 4px 9px; border-radius: 999px; font-size: 12px; margin-left: 8px; background: rgba(148,163,184,.18); color: #e2e8f0; }
.pill.healed { background: rgba(34,197,94,.18); color: #bbf7d0; }
.pill.manual_review, .pill.approved_for_replay { background: rgba(234,179,8,.18); color: #fef08a; }
.pill.failed { background: rgba(239,68,68,.18); color: #fecaca; }
input { background: #020617; color: #bfdbfe; border: 1px solid rgba(148,163,184,.22); border-radius: 12px; padding: 10px 12px; }
@media (max-width: 1100px) { .app-shell { grid-template-columns: 1fr; } .sidebar { position: relative; height: auto; } .cards-grid, .charts-grid, .journey-grid, .two-col, .scenario-grid { grid-template-columns: 1fr; } }
'''
if '.trace-card' not in s:
    s += extra
p.write_text(s)

# 13 add docs
(root/'docs/NEXT_LEVEL_FEATURES.md').write_text('''# Next Level Self Healing Pipeline Features\n\nThis version adds:\n\n1. Failure Simulator tab\n2. Live event journey trace\n3. Reason -> Act -> Verify trace\n4. OpenAI fallback mode\n5. DLQ replay workflow\n6. Pressure test dashboard\n7. RAG evidence visibility\n8. Schema evolution\n9. Better React UI and visualization\n\n## Demo Flow\n\n1. Open http://localhost:3000\n2. Create Kafka topics.\n3. Publish demo dataset or run pressure test.\n4. Watch Live Journey for event movement.\n5. Inspect Reason Act Verify for agent decisions.\n6. Use Failure Simulator, then Pipeline Step Healing.\n7. Review Human Approval and DLQ Replay.\n8. Check PostgreSQL Records and Metrics.\n''')
