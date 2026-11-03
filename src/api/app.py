from __future__ import annotations

from typing import Any, Dict, List

from fastapi import FastAPI, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.dashboard_service import (
    get_pipeline_summary,
    get_consumer_state,
    set_consumer_paused,
    list_incidents,
    list_orders,
    get_agent_decision_traces,
    list_reconciliation_runs,
    update_incident_status,
    run_reconciliation_now,
    peek_dlq,
    replay_payload_to_raw_topic,
)
from src.data_catalog import (
    demo_data_description,
    demo_order_events,
    build_demo_event,
    pressure_test_events,
)
from src.event_gateway import publish_event, publish_events, publish_demo_events
from src.transformations import transform_order_payload, transform_many
from src.pipeline_health import (
    get_pipeline_health,
    heal_safe_pipeline_steps,
    heal_pipeline_component,
    recent_pipeline_step_incidents,
)
from src.failure_simulator import scenarios as failure_scenarios, run_failure_simulation
from src.dashboard_service import (
    list_event_journey,
    list_replay_audit,
    list_schema_versions,
    pressure_test_summary,
    rag_evidence,
)
from src.api.auth import require_role
from src.kafka_lag import get_consumer_lag
from src.tracing import setup_fastapi_tracing
from src.langsmith_observability import langsmith_status
from src.ai_cost import cost_summary
from src.agent_evals import evaluate_agents
from src.multi_agent import compare_agents
from src.alerting import send_alert, list_alerts
from src.approval_workflow import list_approval_requests, decide_approval
from src.log_diagnoser import diagnose_text, diagnose_component_logs
from src.pipeline_learning import action_success_summary
from src.pipeline_metrics import pipeline_healing_metrics
from src.trace_events import list_trace_events

from src.prompt_injection_defense import (
    prompt_injection_test_suite,
    build_safe_llm_context,
)
from src.semantic_cache import semantic_cache_summary, semantic_cache_demo
from src.retrieval_eval import evaluate_retrieval
from src.tool_use_eval import evaluate_tool_use
from src.agent_trajectory import build_agent_trajectory
from src.ai_ops_observatory import ai_ops_observatory
from src.auto_healer_loop import auto_healer_status

app = FastAPI(title="Self Healing Data Pipeline API", version="1.1.0")
setup_fastapi_tracing(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class EventRequest(BaseModel):
    payload: Dict[str, Any]
    transform: bool = False


class BatchEventRequest(BaseModel):
    payloads: List[Dict[str, Any]]
    transform: bool = False


class ConsumerControlRequest(BaseModel):
    paused: bool


class PipelineHealRequest(BaseModel):
    component: str
    action: str | None = None
    approve_risky: bool = False


class FailureSimulationRequest(BaseModel):
    scenario: str


class LogDiagnosisRequest(BaseModel):
    component: str = "all"
    logs: str


class ApprovalDecisionRequest(BaseModel):
    status: str
    reviewer: str = "dashboard"
    reviewer_notes: str = ""


class AlertRequest(BaseModel):
    component: str
    severity: str
    message: str
    channel: str = "dashboard"
    metadata: Dict[str, Any] = {}


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/kafka/lag")
def kafka_lag() -> Dict[str, Any]:
    """Expose consumer lag for the React Metrics tab and Prometheus/Grafana troubleshooting."""
    return get_consumer_lag()


@app.get("/ai/coverage")
def ai_coverage() -> Dict[str, Any]:
    return {
        "covered": [
            "LangGraph state machine for reason act verify healing",
            "Human in the loop interrupt gate for risky repairs",
            "RAG over vectorized incident memory using Chroma",
            "LangChain structured output for controlled decisions",
            "MCP tool abstraction for pipeline tools",
            "Rules first and LLM second repair policy",
            "LLM rate limiting and circuit breaker",
            "PII and schema relevant payload filtering before LLM calls",
            "Agent trace and RAG evidence visibility in dashboard",
            "Prompt injection defense with test suite",
            "Semantic caching for repeated incidents",
            "Retrieval evaluation for vector memory",
            "Tool use evaluation for MCP tools",
            "Agent trajectory dashboard with step timeline",
        ],
        "next_improvements": [
            "model routing across small and large models",
            "prompt version regression tests",
            "online A/B testing of recovery policies",
        ],
    }


@app.get("/ai/langsmith/status")
def ai_langsmith_status() -> Dict[str, Any]:
    return langsmith_status()


@app.get("/ai/costs")
def ai_costs() -> Dict[str, Any]:
    return cost_summary()


@app.get("/ai/evals")
def ai_evals() -> Dict[str, Any]:
    return evaluate_agents()


@app.post("/ai/multi-agent/compare")
def ai_multi_agent_compare(
    request: EventRequest, error_message: str = "validation failed"
) -> Dict[str, Any]:
    return compare_agents(request.payload, error_message=error_message)


@app.get("/ai/security/prompt-injection")
def ai_prompt_injection_suite() -> Dict[str, Any]:
    return prompt_injection_test_suite()


@app.post("/ai/security/safe-context")
def ai_safe_context(
    request: EventRequest, error_message: str = "validation failed"
) -> Dict[str, Any]:
    return build_safe_llm_context(request.payload, error_message)


@app.get("/ai/semantic-cache")
def ai_semantic_cache() -> Dict[str, Any]:
    return semantic_cache_summary()


@app.get("/ai/semantic-cache/demo")
def ai_semantic_cache_demo() -> Dict[str, Any]:
    return semantic_cache_demo()


@app.get("/ai/retrieval-eval")
def ai_retrieval_eval(k: int = Query(default=3, ge=1, le=10)) -> Dict[str, Any]:
    return evaluate_retrieval(k=k)


@app.get("/ai/tool-use-eval")
def ai_tool_use_eval() -> Dict[str, Any]:
    return evaluate_tool_use()


@app.get("/ai/ops-observatory")
def ai_ops_observatory_endpoint() -> Dict[str, Any]:
    return ai_ops_observatory()


@app.get("/ai/trajectory")
def ai_trajectory(limit: int = Query(default=50, ge=1, le=200)) -> Dict[str, Any]:
    return build_agent_trajectory(
        get_pipeline_health(), list_trace_events(limit=limit), limit=limit
    )


@app.get("/auto-healer/status")
def auto_healer_status_endpoint(
    limit: int = Query(default=50, ge=1, le=200)
) -> Dict[str, Any]:
    return auto_healer_status(limit=limit)


@app.get("/data/catalog")
def data_catalog() -> Dict[str, Any]:
    return demo_data_description()


@app.get("/events/demo")
def get_demo_events() -> List[Dict[str, Any]]:
    return demo_order_events()


@app.post("/events")
def send_event(request: EventRequest) -> Dict[str, Any]:
    return publish_event(request.payload, transform=request.transform)


@app.post("/events/batch")
def send_batch(request: BatchEventRequest) -> Dict[str, Any]:
    return publish_events(request.payloads, transform=request.transform)


@app.post("/events/demo")
def send_demo_events(transform: bool = False) -> Dict[str, Any]:
    return publish_demo_events(transform=transform)


@app.post("/transform")
def transform_payload(request: EventRequest) -> Dict[str, Any]:
    transformed, steps = transform_order_payload(request.payload)
    return {"original": request.payload, "transformed": transformed, "steps": steps}


@app.post("/transform/batch")
def transform_batch(request: BatchEventRequest) -> List[Dict[str, Any]]:
    return transform_many(request.payloads)


@app.get("/summary")
def summary() -> Dict[str, Any]:
    return get_pipeline_summary()


@app.get("/consumer/state")
def consumer_state() -> Dict[str, Any]:
    return get_consumer_state()


@app.post("/consumer/state")
def update_consumer_state(request: ConsumerControlRequest) -> Dict[str, Any]:
    return set_consumer_paused(request.paused)


@app.get("/events/test/{scenario}")
def get_test_event(scenario: str) -> Dict[str, Any]:
    return build_demo_event(scenario=scenario, prefix="api")


@app.post("/events/test/{scenario}")
def send_test_event(scenario: str, transform: bool = False) -> Dict[str, Any]:
    return publish_event(
        build_demo_event(scenario=scenario, prefix="api"), transform=transform
    )


class IncidentStatusRequest(BaseModel):
    status: str
    reviewer_notes: str = ""


class ReplayRequest(BaseModel):
    payload: Dict[str, Any]
    reviewer: str = "dashboard"
    reviewer_notes: str = ""
    target_topic: str = "raw_orders"


@app.get("/orders")
def orders(limit: int = Query(default=50, ge=1, le=200)) -> List[Dict[str, Any]]:
    return list_orders(limit=limit)


@app.get("/incidents")
def incidents(
    limit: int = Query(default=50, ge=1, le=200),
    status: str = "all",
) -> List[Dict[str, Any]]:
    return list_incidents(limit=limit, status=status)


@app.get("/agent/traces")
def agent_traces(
    limit: int = Query(default=25, ge=1, le=100),
    status: str = "all",
) -> List[Dict[str, Any]]:
    return get_agent_decision_traces(limit=limit, status=status)


@app.post("/incidents/{incident_id}/status")
def incident_status(
    incident_id: int,
    request: IncidentStatusRequest,
    role: str = Depends(require_role("operator")),
) -> Dict[str, Any]:
    return update_incident_status(incident_id, request.status, request.reviewer_notes)


@app.get("/dlq/peek")
def dlq_peek(max_messages: int = Query(default=5, ge=1, le=20)) -> List[Dict[str, Any]]:
    return peek_dlq(max_messages=max_messages)


@app.post("/dlq/replay")
def dlq_replay(
    request: ReplayRequest, role: str = Depends(require_role("admin"))
) -> Dict[str, Any]:
    return replay_payload_to_raw_topic(
        request.payload, target_topic=request.target_topic
    )


@app.get("/reconciliation/runs")
def reconciliation_runs(
    limit: int = Query(default=20, ge=1, le=100)
) -> List[Dict[str, Any]]:
    return list_reconciliation_runs(limit=limit)


@app.post("/reconciliation/run")
def reconciliation_run_now(
    role: str = Depends(require_role("admin")),
) -> Dict[str, Any]:
    return run_reconciliation_now()


@app.post("/events/pressure-test")
def send_pressure_test(
    total: int = Query(default=1000, ge=1, le=100000)
) -> Dict[str, Any]:
    """Publish a mixed pressure test dataset with valid, healable, manual review, and DLQ records."""
    events = pressure_test_events(total=total)
    result = publish_events(events, transform=False)
    result["total_requested"] = total
    result["expected_distribution"] = {
        "valid_inserted": "about 45 percent",
        "agent_healed": "about 35 percent",
        "manual_review": "about 15 percent",
        "dlq_failed": "about 5 percent plus idempotency conflicts",
    }
    return result


@app.get("/flow/live")
def live_flow() -> Dict[str, Any]:
    """Return dynamic counts for a live Sankey or journey visualization."""
    summary = get_pipeline_summary()
    return {
        "nodes": [
            {
                "id": "kafka",
                "label": "Kafka raw_orders",
                "count": summary.get("orders_count", 0)
                + summary.get("incident_count", 0),
            },
            {
                "id": "postgres",
                "label": "PostgreSQL orders",
                "count": summary.get("orders_count", 0),
            },
            {
                "id": "agent",
                "label": "LangGraph Agent",
                "count": summary.get("incident_count", 0),
            },
            {
                "id": "healed",
                "label": "Agent healed",
                "count": summary.get("healed_count", 0),
            },
            {
                "id": "human",
                "label": "Human approval pending",
                "count": summary.get("manual_review_count", 0),
            },
            {
                "id": "dlq",
                "label": "DLQ quarantined",
                "count": summary.get("dlq_count", 0),
            },
        ],
        "edges": [
            {
                "from": "kafka",
                "to": "postgres",
                "label": "clean insert",
                "count": summary.get("orders_count", 0),
            },
            {
                "from": "kafka",
                "to": "agent",
                "label": "validation failed",
                "count": summary.get("incident_count", 0),
            },
            {
                "from": "agent",
                "to": "healed",
                "label": "reason act verify passed",
                "count": summary.get("healed_count", 0),
            },
            {
                "from": "agent",
                "to": "human",
                "label": "risk gate",
                "count": summary.get("manual_review_count", 0),
            },
            {
                "from": "agent",
                "to": "dlq",
                "label": "quarantine",
                "count": summary.get("dlq_count", 0),
            },
        ],
        "risk_metrics": {
            "low_risk_healed": len(
                [
                    i
                    for i in list_incidents(limit=200, status="healed")
                    if i.get("risk_level") == "low"
                ]
            ),
            "high_risk_manual_review": len(
                [
                    i
                    for i in list_incidents(limit=200, status="manual_review")
                    if i.get("risk_level") == "high"
                ]
            ),
            "failed_or_dlq": summary.get("failed_count", 0),
        },
    }


@app.get("/sql/demo-queries")
def demo_queries() -> Dict[str, Any]:
    return {
        "show_inserted_orders": "SELECT event_id, customer_id, amount, currency, status, created_at FROM orders ORDER BY created_at DESC LIMIT 20;",
        "show_incident_reason_action": "SELECT incident_id, event_id, error_type, healing_action, risk_level, confidence, status, created_at FROM pipeline_incidents ORDER BY created_at DESC LIMIT 20;",
        "healed_records": "SELECT event_id, healing_action, risk_level, confidence, original_payload, healed_payload FROM pipeline_incidents WHERE status = 'healed' ORDER BY created_at DESC;",
        "human_approval_queue": "SELECT incident_id, event_id, error_message, original_payload, healing_action, risk_level FROM pipeline_incidents WHERE status = 'manual_review' ORDER BY created_at DESC;",
        "failed_or_dlq_records": "SELECT incident_id, event_id, error_message, original_payload, healing_action, status FROM pipeline_incidents WHERE status = 'failed' ORDER BY created_at DESC;",
        "risk_summary": "SELECT COALESCE(risk_level, 'unknown') AS risk_level, status, COUNT(*) FROM pipeline_incidents GROUP BY risk_level, status ORDER BY risk_level, status;",
        "agent_actions": "SELECT healing_action, status, COUNT(*) FROM pipeline_incidents GROUP BY healing_action, status ORDER BY healing_action, status;",
    }


@app.get("/action-logs")
def action_logs(limit: int = Query(default=100, ge=1, le=250)) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for inc in list_incidents(limit=limit):
        rows.append(
            {
                "time": inc.get("created_at"),
                "type": "record_incident",
                "event_id": inc.get("event_id"),
                "component": "record_validation",
                "problem": inc.get("error_type"),
                "reason": inc.get("error_message"),
                "action": inc.get("healing_action") or "manual_review_or_dlq",
                "risk_level": inc.get("risk_level"),
                "status": inc.get("status"),
            }
        )
    for inc in recent_pipeline_step_incidents(limit=limit):
        rows.append(
            {
                "time": inc.get("created_at"),
                "type": "pipeline_step_incident",
                "event_id": inc.get("component"),
                "component": inc.get("component"),
                "problem": inc.get("problem_type"),
                "reason": inc.get("reason"),
                "action": inc.get("recovery_action") or "detect_only",
                "risk_level": inc.get("risk_level"),
                "status": inc.get("status"),
            }
        )
    rows.sort(key=lambda r: r.get("time") or "", reverse=True)
    return rows[:limit]


@app.post("/rag/search")
def rag_search(
    request: EventRequest, error_message: str = "manual dashboard search"
) -> Dict[str, Any]:
    from src.mcp_layer.tool_client import call_pipeline_tool

    similar = call_pipeline_tool(
        "search_similar_incidents",
        payload=request.payload,
        error_message=error_message,
        k=5,
    )
    return {"query_payload": request.payload, "similar_incidents": similar}


@app.get("/architecture/journey")
def architecture_journey() -> Dict[str, Any]:
    return {
        "nodes": [
            {"id": "producer", "label": "Producer / Data API", "type": "input"},
            {"id": "kafka", "label": "Kafka raw_orders", "type": "stream"},
            {"id": "consumer", "label": "Python Consumer", "type": "service"},
            {"id": "transform", "label": "Transformation Layer", "type": "logic"},
            {
                "id": "validate",
                "label": "Schema + Business Validation",
                "type": "quality",
            },
            {"id": "postgres", "label": "PostgreSQL orders", "type": "sink"},
            {"id": "agent", "label": "LangGraph Healing Agent", "type": "ai"},
            {"id": "rag", "label": "RAG / Vector Incident Memory", "type": "memory"},
            {"id": "approval", "label": "Human Approval", "type": "review"},
            {"id": "dlq", "label": "Kafka DLQ", "type": "error"},
            {"id": "airflow", "label": "Airflow Reconciliation", "type": "batch"},
            {"id": "metrics", "label": "Prometheus Metrics", "type": "observability"},
        ],
        "edges": [
            ["producer", "kafka"],
            ["kafka", "consumer"],
            ["consumer", "transform"],
            ["transform", "validate"],
            ["validate", "postgres"],
            ["validate", "agent"],
            ["agent", "rag"],
            ["rag", "agent"],
            ["agent", "postgres"],
            ["agent", "approval"],
            ["approval", "kafka"],
            ["agent", "dlq"],
            ["dlq", "airflow"],
            ["postgres", "airflow"],
            ["consumer", "metrics"],
        ],
    }


@app.get("/pipeline/health")
def pipeline_health() -> Dict[str, Any]:
    """Check health of every data flow step: Kafka, consumer, Postgres, Redis, OpenAI, and Airflow."""
    return get_pipeline_health()


@app.post("/pipeline/heal/safe")
def pipeline_heal_safe() -> Dict[str, Any]:
    """Auto heal only safe pipeline step problems and log risky ones for human approval."""
    return heal_safe_pipeline_steps()


@app.post("/pipeline/heal")
def pipeline_heal() -> Dict[str, Any]:
    """Convenience alias used by the UI/demo to auto-heal safe pipeline step problems."""
    return heal_safe_pipeline_steps()


@app.post("/pipeline/heal/component")
def pipeline_heal_component(request: PipelineHealRequest) -> Dict[str, Any]:
    """Heal one pipeline component with an allowlisted recovery action."""
    return heal_pipeline_component(
        request.component, request.action, request.approve_risky
    )


@app.get("/pipeline/incidents")
def pipeline_incidents(
    limit: int = Query(default=50, ge=1, le=250), status: str = "all"
) -> List[Dict[str, Any]]:
    return recent_pipeline_step_incidents(limit=limit, status=status)


@app.get("/pipeline/system-design")
def pipeline_system_design() -> Dict[str, Any]:
    return {
        "title": "Self Healing Data Pipeline Platform",
        "record_healing": [
            "Kafka event fails validation",
            "RAG retrieves similar past incidents",
            "Agent reasons over error, policy, and examples",
            "Agent acts with one safe repair action",
            "Verifier validates the healed payload before PostgreSQL insert",
        ],
        "pipeline_step_healing": [
            "Every data flow component emits health signals",
            "Pipeline healing agent detects component failures",
            "Agent diagnoses root cause from health check, logs, metrics, and RAG memory",
            "Agent executes only allowlisted recovery actions",
            "Risky actions are routed to human approval",
            "Agent verifies component health again after recovery",
        ],
        "components": [
            {
                "component": "Kafka",
                "breaks_when": "topic missing, broker unavailable, lag high",
                "safe_actions": [
                    "create missing topic",
                    "route to DLQ",
                    "request approval for offset reset",
                ],
            },
            {
                "component": "Consumer",
                "breaks_when": "paused, crashed, poison message, missing secret",
                "safe_actions": ["resume consumer", "fallback mode", "manual review"],
            },
            {
                "component": "PostgreSQL",
                "breaks_when": "down, missing table, constraint conflict",
                "safe_actions": [
                    "pause consumer",
                    "run approved migration",
                    "staging table",
                ],
            },
            {
                "component": "Redis",
                "breaks_when": "unavailable, state lost",
                "safe_actions": ["continue without retry memory", "reconnect"],
            },
            {
                "component": "OpenAI",
                "breaks_when": "missing key, timeout, rate limit",
                "safe_actions": ["deterministic fallback", "manual review"],
            },
            {
                "component": "Airflow",
                "breaks_when": "DAG failed, stale reconciliation",
                "safe_actions": ["run reconciliation", "backfill"],
            },
            {
                "component": "Recovery adapters",
                "breaks_when": "operator tooling unavailable",
                "safe_actions": [
                    "dry run action",
                    "request approval",
                    "escalate alert",
                ],
            },
            {
                "component": "Log diagnoser",
                "breaks_when": "unknown error pattern",
                "safe_actions": ["classify logs", "show evidence", "ask human"],
            },
        ],
    }


@app.get("/pipeline/metrics")
def pipeline_metrics_endpoint() -> Dict[str, Any]:
    return pipeline_healing_metrics()


@app.get("/pipeline/recovery-memory")
def recovery_memory(
    component: str | None = None, problem_type: str | None = None
) -> Dict[str, Any]:
    return action_success_summary(component=component, problem_type=problem_type)


@app.get("/pipeline/approvals")
def pipeline_approvals(
    limit: int = Query(default=100, ge=1, le=250), status: str = "all"
) -> List[Dict[str, Any]]:
    return list_approval_requests(limit=limit, status=status)


@app.post("/pipeline/approvals/{approval_id}/decision")
def pipeline_approval_decision(
    approval_id: int,
    request: ApprovalDecisionRequest,
    role: str = Depends(require_role("operator")),
) -> Dict[str, Any]:
    return decide_approval(
        approval_id, request.status, request.reviewer, request.reviewer_notes
    )


@app.get("/pipeline/alerts")
def pipeline_alerts(
    limit: int = Query(default=50, ge=1, le=250)
) -> List[Dict[str, Any]]:
    return list_alerts(limit=limit)


@app.post("/pipeline/alerts")
def pipeline_send_alert(request: AlertRequest) -> Dict[str, Any]:
    return send_alert(
        request.component,
        request.severity,
        request.message,
        request.metadata,
        request.channel,
    )


@app.post("/pipeline/log-diagnosis")
def pipeline_log_diagnosis(request: LogDiagnosisRequest) -> Dict[str, Any]:
    if request.component == "all":
        return {"status": "analyzed", "diagnoses": diagnose_text(request.logs)}
    return diagnose_component_logs(request.component, request.logs)


@app.get("/pipeline/traces")
def pipeline_traces(
    limit: int = Query(default=100, ge=1, le=500)
) -> List[Dict[str, Any]]:
    return list_trace_events(limit=limit)


@app.get("/failure-simulator/scenarios")
def get_failure_scenarios() -> Dict[str, Any]:
    return failure_scenarios()


@app.post("/failure-simulator/run")
def run_failure(request: FailureSimulationRequest) -> Dict[str, Any]:
    return run_failure_simulation(request.scenario)


@app.get("/event-journey")
def event_journey(
    limit: int = Query(default=200, ge=1, le=1000), event_id: str | None = None
) -> List[Dict[str, Any]]:
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
            "v1": {
                "event_id": "evt_1",
                "customer_id": "cust_1",
                "amount": 49.99,
                "currency": "USD",
                "status": "paid",
                "schema_version": 1,
            },
            "v2": {
                "event_id": "evt_2",
                "customer_id": "cust_1",
                "amount_cents": 4999,
                "currency": "USD",
                "order_state": "PAID",
                "schema_version": 2,
            },
        },
    }


@app.get("/pressure-test/summary")
def pressure_summary() -> Dict[str, Any]:
    return pressure_test_summary()


@app.get("/rag/evidence")
def get_rag_evidence(
    limit: int = Query(default=50, ge=1, le=200)
) -> List[Dict[str, Any]]:
    return rag_evidence(limit=limit)
