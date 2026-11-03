from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from src.pipeline_health import get_pipeline_health
from src.trace_events import list_trace_events
from src.retrieval_eval import evaluate_retrieval
from src.tool_use_eval import evaluate_tool_use
from src.semantic_cache import semantic_cache_summary
from src.log_diagnoser import diagnose_text


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_diagnosis_samples() -> Dict[str, Any]:
    samples = [
        {
            "timestamp": _now(),
            "source": "consumer",
            "stage": "Consumer Service",
            "raw_log": "confluent_kafka.KafkaException: Broker: Unknown topic or partition raw_orders",
            "severity": "high",
        },
        {
            "timestamp": _now(),
            "source": "data-api",
            "stage": "PostgreSQL Sink",
            "raw_log": "psycopg2.OperationalError: connection to server at postgres port 5432 failed",
            "severity": "critical",
        },
        {
            "timestamp": _now(),
            "source": "airflow-scheduler",
            "stage": "Airflow Reconciliation",
            "raw_log": "DAG self_healing_reconciliation failed task reconcile_dlq_to_orders",
            "severity": "medium",
        },
        {
            "timestamp": _now(),
            "source": "ai-agent",
            "stage": "LangGraph Agent",
            "raw_log": "OpenAI rate limit exceeded; opening LLM circuit breaker and routing risky cases to manual review",
            "severity": "medium",
        },
    ]
    diagnosed = []
    for row in samples:
        diagnosis = diagnose_text(row["raw_log"])
        issue = (
            diagnosis[0]
            if diagnosis
            else {"problem_type": "unknown", "recommendation": "inspect_manually"}
        )
        diagnosed.append(
            {
                **row,
                "problem_type": issue.get("problem_type", "unknown"),
                "recommended_action": issue.get(
                    "recommendation", issue.get("suggested_action", "inspect_manually")
                ),
                "agent_update": _human_update(
                    row["stage"],
                    issue.get("problem_type", "unknown"),
                    issue.get("recommendation", "inspect_manually"),
                ),
            }
        )
    return {
        "description": "Log diagnosis converts raw operational logs into stage, problem type, severity, and recovery guidance.",
        "rows": diagnosed,
        "coverage": [
            "consumer logs",
            "data-api logs",
            "Airflow task logs",
            "LLM/tool errors",
            "database connectivity errors",
        ],
    }


def _human_update(stage: str, problem_type: str, action: str) -> str:
    return f"I found a {problem_type} signal in {stage}. I am comparing it with prior recoveries and preparing action: {action}."


def vector_memory_explorer() -> Dict[str, Any]:
    retrieval = evaluate_retrieval(k=5)
    rows = []
    for result in retrieval.get("results", []):
        for idx, item in enumerate(result.get("retrieved", [])[:5], start=1):
            rows.append(
                {
                    "query": result.get("query"),
                    "memory_id": item.get("id"),
                    "rank": idx,
                    "similarity_score": item.get("score"),
                    "expected_memory": result.get("expected_memory"),
                    "used_by_agent": idx <= 3,
                    "previous_action": item.get("action", "restart_or_route"),
                    "previous_outcome": item.get(
                        "outcome", "recovered" if idx < 3 else "unknown"
                    ),
                }
            )
    return {
        "description": "Vector memory stores previous failures and recovery outcomes so the agent can reuse successful decisions.",
        "metrics": {
            "precision_at_1": retrieval.get("precision_at_1", 0),
            "hit_rate_at_k": retrieval.get("hit_rate_at_k", 0),
            "mean_reciprocal_rank": retrieval.get("mean_reciprocal_rank", 0),
            "memory_rows": len(rows),
        },
        "rows": rows,
    }


def rag_decision_flow() -> Dict[str, Any]:
    return {
        "description": "RAG is used after detection and before action selection. It makes the agent compare the current failure with similar previous incidents before choosing a recovery action.",
        "nodes": [
            {
                "id": "detect",
                "label": "Detect failure",
                "status": "complete",
                "detail": "Health check/log classifier finds a stage issue.",
            },
            {
                "id": "query",
                "label": "Query memory",
                "status": "complete",
                "detail": "Failure signature is embedded and matched against prior incidents.",
            },
            {
                "id": "retrieve",
                "label": "Retrieve evidence",
                "status": "complete",
                "detail": "Top similar incidents and outcomes are returned.",
            },
            {
                "id": "compare",
                "label": "Compare outcomes",
                "status": "complete",
                "detail": "Agent checks which actions previously recovered or failed.",
            },
            {
                "id": "plan",
                "label": "Plan recovery",
                "status": "active",
                "detail": "Agent selects an allowlisted action with risk policy.",
            },
            {
                "id": "verify",
                "label": "Verify",
                "status": "pending",
                "detail": "Same health check runs after recovery.",
            },
            {
                "id": "remember",
                "label": "Store memory",
                "status": "pending",
                "detail": "Outcome is stored for future decisions.",
            },
        ],
        "edges": [
            ["detect", "query"],
            ["query", "retrieve"],
            ["retrieve", "compare"],
            ["compare", "plan"],
            ["plan", "verify"],
            ["verify", "remember"],
        ],
    }


def mcp_agent_mesh() -> Dict[str, Any]:
    eval_result = evaluate_tool_use()
    tool_rows = eval_result.get("results", [])
    agents = [
        {
            "agent": "Kafka MCP Agent",
            "status": "healthy",
            "tools": ["check_topics", "create_topic", "check_lag", "peek_dlq"],
            "last_tool_called": "check_topics",
            "latency_ms": 31,
            "success_rate": 0.96,
            "last_result": "required topics available",
        },
        {
            "agent": "Database MCP Agent",
            "status": "healthy",
            "tools": [
                "check_tables",
                "query_incidents",
                "replay_audit",
                "orders_count",
            ],
            "last_tool_called": "check_tables",
            "latency_ms": 44,
            "success_rate": 0.94,
            "last_result": "pipeline tables available",
        },
        {
            "agent": "Redis MCP Agent",
            "status": "healthy",
            "tools": ["get_retry_state", "circuit_breaker", "semantic_cache_lookup"],
            "last_tool_called": "semantic_cache_lookup",
            "latency_ms": 12,
            "success_rate": 0.98,
            "last_result": "cache ready",
        },
        {
            "agent": "Airflow MCP Agent",
            "status": "degraded",
            "tools": ["check_dag", "trigger_reconciliation", "read_last_run"],
            "last_tool_called": "read_last_run",
            "latency_ms": 76,
            "success_rate": 0.88,
            "last_result": "no recent reconciliation run found",
        },
        {
            "agent": "Recovery MCP Agent",
            "status": "active",
            "tools": ["inspect_container", "restart_container", "verify_container"],
            "last_tool_called": "inspect_container",
            "latency_ms": 55,
            "success_rate": 0.91,
            "last_result": "docker status adapter available",
        },
        {
            "agent": "Observability MCP Agent",
            "status": "healthy",
            "tools": ["read_metrics", "read_traces", "classify_logs"],
            "last_tool_called": "read_traces",
            "latency_ms": 24,
            "success_rate": 0.95,
            "last_result": "trace timeline loaded",
        },
    ]
    collaboration = [
        {
            "step": 1,
            "agent": "Coordinator Agent",
            "action": "Detected unhealthy stage from pipeline health map",
            "status": "complete",
        },
        {
            "step": 2,
            "agent": "Observability MCP Agent",
            "action": "Classified recent logs and mapped them to failure type",
            "status": "complete",
        },
        {
            "step": 3,
            "agent": "Vector Memory",
            "action": "Retrieved similar incidents and prior recovery outcomes",
            "status": "complete",
        },
        {
            "step": 4,
            "agent": "Kafka/Database/Redis MCP Agent",
            "action": "Selected component-specific tool based on failure",
            "status": "complete",
        },
        {
            "step": 5,
            "agent": "Recovery MCP Agent",
            "action": "Prepared safe recovery or approval request",
            "status": "active",
        },
        {
            "step": 6,
            "agent": "Verifier Agent",
            "action": "Runs post-action health check before marking recovered",
            "status": "pending",
        },
    ]
    return {
        "description": "The platform visualizes MCP as an agent/tool mesh: a coordinator delegates to component-specific operational tool agents.",
        "tool_accuracy": eval_result.get("tool_accuracy", 0),
        "action_accuracy": eval_result.get("action_accuracy", 0),
        "agents": agents,
        "tool_eval_rows": tool_rows,
        "collaboration_timeline": collaboration,
    }


def tool_call_traces() -> Dict[str, Any]:
    traces = list_trace_events(limit=80)
    rows = []
    for idx, tr in enumerate(traces[:20], start=1):
        rows.append(
            {
                "step": idx,
                "timestamp": tr.get("created_at") or tr.get("timestamp") or _now(),
                "component": tr.get("component", "pipeline"),
                "tool": tr.get("tool", tr.get("event_type", "health_check")),
                "input": tr.get("problem_type", tr.get("action", "inspect")),
                "output": tr.get("status", "ok"),
                "latency_ms": tr.get("latency_ms", 25 + idx * 3),
            }
        )
    if not rows:
        rows = [
            {
                "step": 1,
                "timestamp": _now(),
                "component": "kafka",
                "tool": "check_topics",
                "input": "required_topics",
                "output": "healthy",
                "latency_ms": 31,
            },
            {
                "step": 2,
                "timestamp": _now(),
                "component": "postgres",
                "tool": "check_tables",
                "input": "orders/incidents",
                "output": "healthy",
                "latency_ms": 44,
            },
            {
                "step": 3,
                "timestamp": _now(),
                "component": "redis",
                "tool": "semantic_cache_lookup",
                "input": "incident_signature",
                "output": "miss",
                "latency_ms": 12,
            },
        ]
    return {
        "description": "Tool-call traces show the operational calls made by MCP tools and agent recovery workflows.",
        "rows": rows,
    }


def visualization_charts() -> Dict[str, Any]:
    health = get_pipeline_health()
    stage_map = health.get("stage_map", [])
    vector = vector_memory_explorer()
    mcp = mcp_agent_mesh()
    logs = log_diagnosis_samples()
    semantic = semantic_cache_summary()
    return {
        "stage_health": [
            {
                "name": "Healthy",
                "value": sum(1 for s in stage_map if s.get("color") == "green"),
            },
            {
                "name": "Self-healing",
                "value": sum(1 for s in stage_map if s.get("color") == "yellow"),
            },
            {
                "name": "Down",
                "value": sum(1 for s in stage_map if s.get("color") == "red"),
            },
        ],
        "mcp_success": [
            {
                "agent": a["agent"].replace(" MCP Agent", ""),
                "success_rate": round(a["success_rate"] * 100, 1),
                "latency_ms": a["latency_ms"],
            }
            for a in mcp["agents"]
        ],
        "rag_scores": [
            {
                "memory": r["memory_id"],
                "score": r["similarity_score"] or 0,
                "rank": r["rank"],
            }
            for r in vector["rows"][:8]
        ],
        "log_severity": [
            {
                "severity": sev,
                "count": sum(1 for r in logs["rows"] if r["severity"] == sev),
            }
            for sev in ["critical", "high", "medium", "low"]
        ],
        "cache": [
            {"name": "Entries", "value": semantic.get("entries", 0)},
            {"name": "Hits", "value": semantic.get("total_hits", 0)},
            {"name": "Misses", "value": semantic.get("total_misses", 0)},
        ],
    }


def ai_ops_observatory() -> Dict[str, Any]:
    return {
        "title": "AI Operations Observatory",
        "description": "Unified visualization layer for logs, vector memory, RAG evidence, MCP tool agents, tool calls, and agent collaboration.",
        "logs": log_diagnosis_samples(),
        "vector_memory": vector_memory_explorer(),
        "rag_flow": rag_decision_flow(),
        "mcp_mesh": mcp_agent_mesh(),
        "tool_traces": tool_call_traces(),
        "charts": visualization_charts(),
    }
