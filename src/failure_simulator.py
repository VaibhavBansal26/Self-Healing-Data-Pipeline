from __future__ import annotations

from typing import Any, Dict
from confluent_kafka.admin import AdminClient, NewTopic
from src.config import KAFKA_BOOTSTRAP_SERVERS, DLQ_TOPIC, RAW_TOPIC, REDIS_HOST, REDIS_PORT
from src.dashboard_service import set_consumer_paused
from src.event_gateway import publish_event
from src.data_catalog import build_demo_event
from src.db import insert_pipeline_step_incident, update_pipeline_step_incident
from src.recovery_adapters.docker_recovery import restart_service, start_service

SCENARIOS = [
    {"id": "missing_dlq_topic", "label": "Delete DLQ topic", "risk": "medium", "description": "Deletes dead_letter_events so pipeline step healing can recreate it."},
    {"id": "pause_consumer", "label": "Pause consumer", "risk": "low", "description": "Sets Redis pause flag so consumer stops processing until healed."},
    {"id": "openai_unavailable", "label": "Simulate OpenAI unavailable", "risk": "low", "description": "Enables deterministic fallback flag so the system demonstrates degraded LLM mode."},
    {"id": "unsupported_schema_event", "label": "Publish unsupported schema", "risk": "medium", "description": "Sends schema_version 99 event to demonstrate schema evolution handling."},
    {"id": "transformation_exception", "label": "Publish transformation exception candidate", "risk": "low", "description": "Sends malformed amount to show manual review or DLQ."},
    {"id": "consumer_container_down", "label": "Stop/restart consumer container", "risk": "high", "description": "Creates a consumer-down incident and returns a dry-run Docker recovery command unless enabled."},
    {"id": "postgres_unavailable", "label": "Postgres unavailable", "risk": "high", "description": "Creates a DB outage incident and asks the pipeline agent to pause writes and recover safely."},
    {"id": "redis_unavailable", "label": "Redis unavailable", "risk": "medium", "description": "Creates Redis degraded-mode incident and verifies fallback behavior."},
    {"id": "high_consumer_lag", "label": "High Kafka lag", "risk": "medium", "description": "Publishes a burst of events to create backlog and test lag detection."},
    {"id": "airflow_dag_failed", "label": "Airflow DAG failed", "risk": "medium", "description": "Creates reconciliation failure memory so the agent can retry reconciliation."},
    {"id": "stuck_dlq_replay", "label": "Stuck DLQ replay", "risk": "high", "description": "Creates an approval-required replay incident."},
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

    if scenario == "consumer_container_down":
        incident_id = insert_pipeline_step_incident("consumer", "container_down_simulation", "Failure simulator marked consumer as down. Agent should restart or resume consumer after approval if needed.", {"service": "consumer"}, "restart_consumer", risk_level="high", status="simulated", requires_human_approval=True)
        return {"scenario": scenario, "step_incident_id": incident_id, "docker_recovery_preview": restart_service("consumer")}
    if scenario == "postgres_unavailable":
        incident_id = insert_pipeline_step_incident("postgres", "connection_failure_simulation", "Failure simulator created a database outage incident. Agent should pause consumer, retry DB, and verify recovery.", {"service": "postgres"}, "pause_consumer_and_retry_db", risk_level="high", status="simulated")
        return {"scenario": scenario, "step_incident_id": incident_id, "docker_recovery_preview": start_service("postgres")}
    if scenario == "redis_unavailable":
        incident_id = insert_pipeline_step_incident("redis", "connection_failure_simulation", "Failure simulator created a Redis outage incident. Pipeline should continue in degraded memory mode.", {"service": "redis"}, "continue_without_retry_memory", risk_level="medium", status="simulated")
        return {"scenario": scenario, "step_incident_id": incident_id}
    if scenario == "high_consumer_lag":
        events = [build_demo_event("amount_as_string", prefix=f"lag_{i}") for i in range(250)]
        from src.event_gateway import publish_events
        result = publish_events(events)
        incident_id = insert_pipeline_step_incident("consumer", "high_consumer_lag_simulation", "Failure simulator published a burst of events to increase consumer lag.", {"event_count": len(events)}, "restart_consumer", risk_level="medium", status="simulated")
        return {"scenario": scenario, "step_incident_id": incident_id, "publish_result": result}
    if scenario == "airflow_dag_failed":
        incident_id = insert_pipeline_step_incident("airflow", "dag_failed_simulation", "Failure simulator created an Airflow reconciliation failure incident.", {"dag": "daily_reconciliation"}, "run_reconciliation", risk_level="medium", status="simulated")
        return {"scenario": scenario, "step_incident_id": incident_id}
    if scenario == "stuck_dlq_replay":
        incident_id = insert_pipeline_step_incident("kafka", "stuck_dlq_replay_simulation", "Failure simulator created a stuck DLQ replay incident requiring approval.", {"topic": DLQ_TOPIC}, "manual_review", risk_level="high", status="simulated", requires_human_approval=True)
        return {"scenario": scenario, "step_incident_id": incident_id}
    raise ValueError(f"Unsupported failure simulation: {scenario}")
