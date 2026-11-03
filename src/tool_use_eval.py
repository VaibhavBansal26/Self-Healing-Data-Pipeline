from __future__ import annotations

from typing import Any, Dict, List

TOOL_CASES = [
    {"problem":"postgres connection refused", "component":"postgres", "expected_tool":"query_recent_incidents", "expected_action":"retry_postgres_connection"},
    {"problem":"kafka topic raw_orders missing", "component":"kafka", "expected_tool":"create_missing_topic", "expected_action":"create_kafka_topic"},
    {"problem":"dead letter queue has stuck events", "component":"dlq", "expected_tool":"peek_dlq", "expected_action":"inspect_dlq"},
    {"problem":"redis retry state unavailable", "component":"redis", "expected_tool":"get_redis_retry_count", "expected_action":"fallback_in_memory"},
    {"problem":"similar previous bad status incident", "component":"rag", "expected_tool":"search_similar_incidents", "expected_action":"retrieve_memory"},
    {"problem":"daily reconciliation failed", "component":"airflow", "expected_tool":"run_reconciliation", "expected_action":"rerun_reconciliation"},
]


def select_tool(problem: str, component: str) -> Dict[str, str]:
    text = f"{component} {problem}".lower()
    if "topic" in text or "kafka" in text:
        return {"tool":"create_missing_topic", "action":"create_kafka_topic"}
    if "dlq" in text or "dead letter" in text:
        return {"tool":"peek_dlq", "action":"inspect_dlq"}
    if "redis" in text:
        return {"tool":"get_redis_retry_count", "action":"fallback_in_memory"}
    if "similar" in text or "rag" in text or "previous" in text:
        return {"tool":"search_similar_incidents", "action":"retrieve_memory"}
    if "airflow" in text or "reconciliation" in text:
        return {"tool":"run_reconciliation", "action":"rerun_reconciliation"}
    if "postgres" in text or "database" in text:
        return {"tool":"query_recent_incidents", "action":"retry_postgres_connection"}
    return {"tool":"query_recent_incidents", "action":"diagnose_unknown"}


def evaluate_tool_use() -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []
    correct_tool = 0
    correct_action = 0
    for case in TOOL_CASES:
        selected = select_tool(case["problem"], case["component"])
        tool_ok = selected["tool"] == case["expected_tool"]
        action_ok = selected["action"] == case["expected_action"]
        correct_tool += int(tool_ok)
        correct_action += int(action_ok)
        results.append({**case, **selected, "tool_ok": tool_ok, "action_ok": action_ok})
    n = len(TOOL_CASES)
    return {
        "cases": n,
        "tool_accuracy": round(correct_tool / n, 4),
        "action_accuracy": round(correct_action / n, 4),
        "purpose": "Evaluates whether MCP/tool routing chooses the right operational tool for a given pipeline failure.",
        "results": results,
    }
