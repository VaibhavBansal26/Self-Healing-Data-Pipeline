from __future__ import annotations

import re
from typing import Any, Dict, List

LOG_PATTERNS = [
    (
        "postgres",
        "db_connection_failure",
        "high",
        r"connection.*(refused|failed)|database .* does not exist|OperationalError",
        "Pause writes, check database readiness, and replay buffered events after recovery.",
    ),
    (
        "kafka",
        "kafka_topic_missing",
        "medium",
        r"UnknownTopic|topic .* not present|missing_topic",
        "Create the missing topic through Kafka Admin and verify producer/consumer resume.",
    ),
    (
        "consumer",
        "consumer_crash",
        "high",
        r"Traceback|Exception in consumer|consumer.*stopped",
        "Restart consumer and inspect poison message or dependency failure.",
    ),
    (
        "redis",
        "redis_connection_error",
        "medium",
        r"Redis.*(Error|Connection)|connection refused.*6379",
        "Switch to in memory fallback and reconnect Redis.",
    ),
    (
        "openai",
        "llm_timeout",
        "medium",
        r"OpenAI|RateLimit|timeout|APIError",
        "Open circuit breaker and route unresolved records to manual review.",
    ),
    (
        "airflow",
        "airflow_dag_failed",
        "medium",
        r"DAG.*failed|Task failed|airflow",
        "Retry reconciliation DAG and inspect failed task logs.",
    ),
]


def diagnose_text(text: str) -> List[Dict[str, Any]]:
    diagnoses: List[Dict[str, Any]] = []
    for component, pattern, severity, regex, recommendation in LOG_PATTERNS:
        if re.search(regex, text, flags=re.IGNORECASE):
            sample = text[-800:]
            diagnoses.append(
                {
                    "component": component,
                    "pattern": pattern,
                    "severity": severity,
                    "sample": sample,
                    "recommendation": recommendation,
                }
            )
    return diagnoses


def diagnose_component_logs(component: str, text: str = "") -> Dict[str, Any]:
    matches = [
        m
        for m in diagnose_text(text)
        if m["component"] == component or component == "all"
    ]
    if not matches:
        return {
            "component": component,
            "status": "no_known_error_pattern",
            "diagnoses": [],
        }
    return {"component": component, "status": "patterns_detected", "diagnoses": matches}


def human_update_from_diagnosis(diagnosis: Dict[str, Any]) -> str:
    return f"I found {diagnosis.get('pattern')} in {diagnosis.get('component')} logs. I recommend: {diagnosis.get('recommendation')}"
