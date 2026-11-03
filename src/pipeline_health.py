from __future__ import annotations

import os
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

from confluent_kafka.admin import AdminClient

from src.config import (
    KAFKA_BOOTSTRAP_SERVERS,
    RAW_TOPIC,
    DLQ_TOPIC,
    REDIS_HOST,
    REDIS_PORT,
    POSTGRES_CONFIG,
    AUTO_HEAL_PIPELINE_STEPS,
)
from src.db import (
    get_db_connection,
    insert_pipeline_step_incident,
    update_pipeline_step_incident,
    list_pipeline_step_incidents,
)
from src.alerting import send_alert
from src.heal_budget import HealBudget
from src.approval_workflow import create_approval_request, find_pending_approval
from src.log_diagnoser import diagnose_component_logs
from src.pipeline_learning import remember_recovery, action_success_summary
from src.trace_events import trace_event


@dataclass
class ComponentHealth:
    component: str
    status: str
    problem_type: str = "none"
    reason: str = "healthy"
    detected_state: Optional[Dict[str, Any]] = None
    risk_level: str = "low"
    suggested_action: str = "none"
    requires_human_approval: bool = False
    agent_plan: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Fields kept from a past incident when it is quoted as evidence. Quoting whole rows
# would embed their own detected_state/verification_result, which already contain
# earlier evidence, so every new incident would be about 3x the size of the last.
_EVIDENCE_FIELDS = (
    "step_incident_id",
    "component",
    "problem_type",
    "recovery_action",
    "risk_level",
    "status",
    "created_at",
)


def summarize_incident(row: Dict[str, Any]) -> Dict[str, Any]:
    return {key: row.get(key) for key in _EVIDENCE_FIELDS}


class PipelineHealingAgent:
    """Self-healing agent for *pipeline* failures, not only bad records.

    The agent does more than a raw health check:
    1. Detects symptoms from health checks, metrics, and control state.
    2. Retrieves previous recovery decisions from incident memory.
    3. Calls read-only MCP-style tools for extra context where useful.
    4. Plans one allowlisted recovery action with risk and approval rules.
    5. Executes the action only when it is safe or explicitly approved.
    6. Verifies the same component again and stores the outcome as memory.

    This keeps the demo safe locally while still showing the AI engineering idea:
    health signal -> memory/context -> decision -> tool action -> verification.
    """

    def __init__(self):
        self.kafka_admin = AdminClient({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})
        self.budget = HealBudget.from_env()

    # ---------- Health checks ----------
    def check_kafka_topics(self) -> List[ComponentHealth]:
        required = [RAW_TOPIC, DLQ_TOPIC]
        try:
            topics = set(self.kafka_admin.list_topics(timeout=5).topics.keys())
        except Exception as exc:
            return [
                ComponentHealth(
                    component="kafka",
                    status="unhealthy",
                    problem_type="broker_unavailable",
                    reason=f"Could not list Kafka topics: {exc}",
                    detected_state={"bootstrap": KAFKA_BOOTSTRAP_SERVERS},
                    risk_level="high",
                    suggested_action="manual_review",
                    requires_human_approval=True,
                )
            ]
        results = []
        for topic in required:
            if topic not in topics:
                results.append(
                    ComponentHealth(
                        component="kafka",
                        status="unhealthy",
                        problem_type="missing_topic",
                        reason=f"Required Kafka topic {topic} is missing.",
                        detected_state={
                            "existing_topics": sorted(topics),
                            "missing_topic": topic,
                        },
                        risk_level="low",
                        suggested_action="create_missing_topic",
                        requires_human_approval=False,
                    )
                )
        if not results:
            state = {"topics": sorted(topics), "required_topics": required}
            try:
                from src.mcp_layer.tool_client import call_pipeline_tool

                state["dlq_context_from_mcp"] = call_pipeline_tool("get_dlq_count")
            except Exception as exc:
                state["dlq_context_from_mcp"] = {"available": False, "error": str(exc)}
            results.append(ComponentHealth("kafka", "healthy", detected_state=state))
        return results

    def check_postgres(self) -> ComponentHealth:
        required_tables = {
            "orders",
            "pipeline_incidents",
            "dlq_replay_audit",
            "reconciliation_runs",
            "pipeline_step_incidents",
        }
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT table_name FROM information_schema.tables WHERE table_schema='public';"
                    )
                    tables = {r[0] for r in cur.fetchall()}
                    missing = sorted(required_tables - tables)
                    if missing:
                        return ComponentHealth(
                            component="postgres",
                            status="unhealthy",
                            problem_type="missing_table",
                            reason=f"PostgreSQL is reachable but missing required tables: {missing}",
                            detected_state={
                                "existing_tables": sorted(tables),
                                "missing_tables": missing,
                            },
                            risk_level="medium",
                            suggested_action="run_safe_migration",
                            requires_human_approval=True,
                        )
                    cur.execute("SELECT COUNT(*) FROM orders;")
                    orders_count = cur.fetchone()[0]
            return ComponentHealth(
                "postgres",
                "healthy",
                detected_state={
                    "orders_count": orders_count,
                    "tables": sorted(required_tables),
                },
            )
        except Exception as exc:
            return ComponentHealth(
                component="postgres",
                status="unhealthy",
                problem_type="connection_failure",
                reason=f"PostgreSQL connection failed: {exc}",
                detected_state={
                    "config_host": POSTGRES_CONFIG.get("host"),
                    "config_port": POSTGRES_CONFIG.get("port"),
                },
                risk_level="high",
                suggested_action="pause_consumer_and_retry_db",
                requires_human_approval=False,
            )

    def check_redis(self) -> ComponentHealth:
        try:
            import redis

            client = redis.Redis(
                host=REDIS_HOST, port=REDIS_PORT, decode_responses=True
            )
            pong = client.ping()
            paused = client.get("consumer:paused") == "true"
            fallback_mode = client.get("llm:fallback_mode")
            return ComponentHealth(
                "redis",
                "healthy",
                detected_state={
                    "ping": pong,
                    "consumer_paused": paused,
                    "llm_fallback_mode": fallback_mode,
                },
            )
        except Exception as exc:
            return ComponentHealth(
                component="redis",
                status="degraded",
                problem_type="connection_failure",
                reason=f"Redis unavailable: {exc}. Pipeline can continue without retry memory but loses pause/resume state.",
                detected_state={"host": REDIS_HOST, "port": REDIS_PORT},
                risk_level="medium",
                suggested_action="restart_redis_container",
                requires_human_approval=False,
            )

    def check_openai(self) -> ComponentHealth:
        key = os.getenv("OPENAI_API_KEY", "")
        if not key:
            return ComponentHealth(
                component="openai",
                status="degraded",
                problem_type="missing_secret",
                reason="OPENAI_API_KEY is missing. Agent cannot call OpenAI and should use deterministic fallback or manual review.",
                detected_state={"OPENAI_API_KEY_present": False},
                risk_level="medium",
                suggested_action="enable_deterministic_fallback",
                requires_human_approval=False,
            )
        return ComponentHealth(
            "openai",
            "healthy",
            detected_state={"OPENAI_API_KEY_present": True, "mode": "llm_enabled"},
        )

    def check_consumer_state(self) -> ComponentHealth:
        """Check both the logical pause flag and the actual Docker container.

        The earlier version only checked Redis pause state, which missed the real
        failure case where `healing_consumer` was stopped. This makes the stage map
        reflect the actual processing stage.
        """
        paused = False
        redis_error = None
        try:
            import redis

            client = redis.Redis(
                host=REDIS_HOST, port=REDIS_PORT, decode_responses=True
            )
            paused = client.get("consumer:paused") == "true"
        except Exception as exc:
            redis_error = str(exc)

        try:
            from src.docker_runtime import get_container_status

            docker_state = get_container_status("consumer")
        except Exception as exc:
            docker_state = {
                "status": "unknown",
                "running": False,
                "reason": "docker_check_failed",
                "error": str(exc),
            }

        detected = {
            "consumer_paused": paused,
            "redis_state_error": redis_error,
            "docker": docker_state,
        }

        if (
            docker_state.get("status") in {"unhealthy", "down"}
            or docker_state.get("running") is False
            and docker_state.get("status") != "unknown"
        ):
            return ComponentHealth(
                component="consumer",
                status="unhealthy",
                problem_type="consumer_container_down",
                reason="The consumer container is not running, so Kafka events can be accepted but will not be processed into PostgreSQL until the consumer recovers.",
                detected_state=detected,
                risk_level="medium",
                suggested_action="restart_consumer_container",
                requires_human_approval=False,
            )

        if docker_state.get("status") in {"degraded", "unknown"}:
            return ComponentHealth(
                component="consumer",
                status="degraded",
                problem_type="consumer_runtime_unknown",
                reason=f"Consumer runtime status is {docker_state.get('status')}: {docker_state.get('reason')}",
                detected_state=detected,
                risk_level="medium",
                suggested_action="check_consumer_logs",
                requires_human_approval=True,
            )

        if paused:
            return ComponentHealth(
                component="consumer",
                status="degraded",
                problem_type="paused",
                reason="Consumer is paused through dashboard/API control.",
                detected_state=detected,
                risk_level="low",
                suggested_action="resume_consumer",
                requires_human_approval=False,
            )

        return ComponentHealth("consumer", "healthy", detected_state=detected)

    def check_airflow(self) -> ComponentHealth:
        """Check Airflow scheduler/webserver container state plus reconciliation table access."""
        try:
            from src.docker_runtime import get_container_status

            web = get_container_status("airflow-webserver")
            sched = get_container_status("airflow-scheduler")
        except Exception as exc:
            web = {
                "status": "unknown",
                "reason": "docker_check_failed",
                "error": str(exc),
            }
            sched = {
                "status": "unknown",
                "reason": "docker_check_failed",
                "error": str(exc),
            }

        runs = None
        db_error = None
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM reconciliation_runs;")
                    runs = cur.fetchone()[0]
        except Exception as exc:
            db_error = str(exc)

        detected = {
            "reconciliation_runs": runs,
            "database_error": db_error,
            "webserver": web,
            "scheduler": sched,
        }
        down = [
            name
            for name, state in {"webserver": web, "scheduler": sched}.items()
            if state.get("status") in {"unhealthy", "down"}
            or (state.get("running") is False and state.get("status") != "unknown")
        ]
        unknown = [
            name
            for name, state in {"webserver": web, "scheduler": sched}.items()
            if state.get("status") == "unknown"
        ]

        if down:
            return ComponentHealth(
                component="airflow",
                status="unhealthy",
                problem_type="airflow_service_down",
                reason=f"Airflow service(s) are down: {', '.join(down)}. Scheduled reconciliation may not run, but manual/API reconciliation can still be used.",
                detected_state=detected,
                risk_level="medium",
                suggested_action="restart_airflow_services",
                requires_human_approval=False,
            )
        if unknown or db_error:
            return ComponentHealth(
                component="airflow",
                status="degraded",
                problem_type="reconciliation_unavailable",
                reason=f"Airflow or reconciliation health is degraded. unknown={unknown}, db_error={db_error}",
                detected_state=detected,
                risk_level="medium",
                suggested_action="run_reconciliation",
                requires_human_approval=False,
            )
        return ComponentHealth(
            "airflow",
            "healthy",
            detected_state={**detected, "check": "docker + database backed"},
        )

    def check_control_plane(self) -> ComponentHealth:
        try:
            from src.docker_runtime import get_many_container_statuses

            states = get_many_container_statuses(
                ["data-api", "frontend", "metrics", "prometheus"]
            )
        except Exception as exc:
            return ComponentHealth(
                component="control_plane",
                status="degraded",
                problem_type="docker_status_unavailable",
                reason=f"Could not inspect dashboard/control-plane containers: {exc}",
                detected_state={"error": str(exc)},
                risk_level="low",
                suggested_action="check_control_plane_logs",
                requires_human_approval=False,
            )
        bad = {
            name: state
            for name, state in states.items()
            if state.get("status") not in {"healthy"}
        }
        if bad:
            return ComponentHealth(
                component="control_plane",
                status="degraded",
                problem_type="control_plane_component_degraded",
                reason="One or more observability/control-plane services are degraded.",
                detected_state={"services": states, "bad": bad},
                risk_level="low",
                suggested_action="restart_control_plane_service",
                requires_human_approval=False,
            )
        return ComponentHealth(
            "control_plane", "healthy", detected_state={"services": states}
        )

    # ---------- Agent planning and memory ----------
    def _memory_for_component(
        self,
        component: str,
        problem_type: Optional[str] = None,
        action: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            rows = [
                r
                for r in list_pipeline_step_incidents(limit=100)
                if r.get("component") == component
            ]
        except Exception as exc:
            return {
                "available": False,
                "error": str(exc),
                "similar_decisions": [],
                "success_rate_for_action": None,
            }
        if problem_type:
            similar = [r for r in rows if r.get("problem_type") == problem_type]
        else:
            similar = rows
        if action:
            action_rows = [r for r in similar if r.get("recovery_action") == action]
        else:
            action_rows = similar
        healed = sum(1 for r in action_rows if r.get("status") == "healed")
        failed = sum(1 for r in action_rows if r.get("status") == "failed")
        total = healed + failed
        return {
            "available": True,
            "component": component,
            "problem_type": problem_type,
            "candidate_action": action,
            "similar_decisions": [summarize_incident(r) for r in similar[:5]],
            "success_rate_for_action": round(healed / total, 3) if total else None,
            "healed_count": healed,
            "failed_count": failed,
        }

    def _read_only_tool_context(self, component: str) -> Dict[str, Any]:
        """Use MCP/local tools for context, not for mutation during planning."""
        context: Dict[str, Any] = {"mcp_tools_used": []}
        try:
            from src.mcp_layer.tool_client import call_pipeline_tool

            if component in {"kafka", "airflow"}:
                context["dlq_count"] = call_pipeline_tool("get_dlq_count")
                context["mcp_tools_used"].append("get_dlq_count")
            if component in {"postgres", "consumer", "airflow"}:
                context["recent_record_incidents"] = call_pipeline_tool(
                    "query_recent_incidents", limit=5
                )
                context["mcp_tools_used"].append("query_recent_incidents")
        except Exception as exc:
            context["mcp_context_error"] = str(exc)
        return context

    def _agent_plan(self, component_health: ComponentHealth) -> Dict[str, Any]:
        memory = self._memory_for_component(
            component_health.component,
            component_health.problem_type,
            component_health.suggested_action,
        )
        tool_context = self._read_only_tool_context(component_health.component)
        log_context = diagnose_component_logs(
            component_health.component,
            str(component_health.reason) + " " + str(component_health.detected_state),
        )
        learning_summary = action_success_summary(
            component_health.component, component_health.problem_type
        )
        past_success = memory.get("success_rate_for_action")
        require_approval = component_health.requires_human_approval
        if (
            past_success is not None
            and past_success < 0.5
            and component_health.risk_level != "low"
        ):
            require_approval = True
        action = component_health.suggested_action
        decision = {
            "agent_name": "pipeline_recovery_planner",
            "decision_type": "pipeline_step_healing",
            "diagnosis": component_health.reason,
            "proposed_action": action,
            "allowed_action": action
            in {
                "create_missing_topic",
                "resume_consumer",
                "enable_deterministic_fallback",
                "pause_consumer_and_retry_db",
                "continue_without_retry_memory",
                "restart_redis_container",
                "run_reconciliation",
                "run_safe_migration",
                "manual_review",
                "check_consumer_logs",
                "restart_consumer_container",
                "restart_airflow_services",
                "restart_control_plane_service",
                "check_control_plane_logs",
                "none",
            },
            "risk_level": component_health.risk_level,
            "requires_human_approval": require_approval,
            "memory_evidence": memory,
            "mcp_tool_context": tool_context,
            "log_diagnosis": log_context,
            "learning_summary": learning_summary,
            "why_ai_agent_is_useful": [
                "Health checks only say what is broken; the agent chooses a recovery action using policy, component risk, MCP tool context, and previous outcomes.",
                "RAG/memory prevents repeating recovery actions that failed before for the same component and problem.",
                "MCP standardizes how the agent reads operational tools like DLQ count, recent incidents, and reconciliation without hard wiring every tool into the graph.",
                "Reason Act Verify requires verification after the action and stores the result for future decisions.",
            ],
        }
        return decision

    def _attach_agent_plans(
        self, checks: List[ComponentHealth]
    ) -> List[ComponentHealth]:
        planned = []
        for c in checks:
            if c.status != "healthy":
                c.agent_plan = self._agent_plan(c)
                c.requires_human_approval = bool(
                    c.agent_plan.get("requires_human_approval")
                )
            planned.append(c)
        return planned

    def full_health_check(self) -> Dict[str, Any]:
        checks: List[ComponentHealth] = []
        checks.extend(self.check_kafka_topics())
        checks.append(self.check_postgres())
        checks.append(self.check_redis())
        checks.append(self.check_openai())
        checks.append(self.check_consumer_state())
        checks.append(self.check_airflow())
        checks.append(self.check_control_plane())
        checks = self._attach_agent_plans(checks)
        unhealthy = [
            c for c in checks if c.status in {"unhealthy", "degraded", "unknown"}
        ]
        overall = (
            "healthy"
            if not unhealthy
            else (
                "degraded"
                if all(c.status != "unhealthy" for c in unhealthy)
                else "unhealthy"
            )
        )
        component_dicts = [c.to_dict() for c in checks]
        latest_memory = []
        try:
            latest_memory = list_pipeline_step_incidents(limit=8)
        except Exception:
            latest_memory = []
        stage_map = self._build_stage_map(component_dicts, latest_memory)
        agent_status = self._build_agent_status(component_dicts, latest_memory)
        return {
            "overall_status": overall,
            "components": component_dicts,
            "stage_map": stage_map,
            "agent_status": agent_status,
            "unhealthy_count": len(unhealthy),
            "complete_pipeline_coverage": [
                "Event producer and FastAPI gateway",
                "Kafka raw topic and DLQ topic",
                "Consumer processing loop and pause/resume state",
                "Rules based deterministic repair",
                "RAG/vector incident memory",
                "LangGraph recovery planner and verifier",
                "MCP tool layer for operational context",
                "Human approval for risky recovery",
                "PostgreSQL sink and incident store",
                "Airflow reconciliation",
                "Redis state, retry memory, and circuit breakers",
                "Prometheus metrics and dashboard health",
                "Real Docker container status for consumer, Airflow, API, frontend, metrics, and Prometheus",
                "Docker/Kubernetes/Airflow/Kafka recovery adapters",
                "Log based diagnosis and human spoken agent updates",
                "Alerting, approval queue, and recovery success memory",
            ],
            "agent_value": {
                "not_just_health_checks": "Health checks detect symptoms. The pipeline healing agent decides what to do, retrieves previous decisions, calls MCP tools for extra context, executes allowlisted recovery actions, verifies recovery, and stores the outcome as future memory.",
                "rag_and_memory": "Previous pipeline step incidents are reused as operational memory to avoid repeated failed remediations.",
                "mcp": "MCP/local tools provide a standard tool interface for DLQ, incident, Redis, reconciliation, and replay operations.",
                "human_gate": "Risky or historically unsuccessful actions are routed to manual approval instead of being executed blindly.",
            },
            "reason_act_verify": {
                "reason": "Health checks inspect Kafka, Postgres, Redis, OpenAI, real Docker container state, Consumer pause/running state, Airflow scheduler/webserver state, memory, and MCP tool context.",
                "act": "The agent selects one allowlisted recovery action using policy plus previous decisions memory and MCP tool context.",
                "verify": "After each recovery action, the same component health check runs again before the incident is marked healed.",
            },
        }

    def _build_agent_status(
        self, components: List[Dict[str, Any]], latest_memory: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        unhealthy = [c for c in components if c.get("status") != "healthy"]
        waiting = [c for c in unhealthy if c.get("requires_human_approval")]
        if waiting:
            state = "waiting_for_human_approval"
            badge_color = "yellow"
            headline = f"I found {len(waiting)} risky pipeline recovery action that needs approval before I continue."
        elif unhealthy:
            state = "detecting_and_planning"
            badge_color = "blue"
            headline = f"I found {len(unhealthy)} pipeline stage needing attention and prepared safe recovery plans."
        else:
            state = "sleeping"
            badge_color = "green"
            headline = "I am sleeping. All monitored pipeline stages are healthy."
        updates = []
        if unhealthy:
            for c in unhealthy[:5]:
                plan = c.get("agent_plan") or {}
                action = plan.get("proposed_action") or c.get("suggested_action")
                updates.append(
                    f"I checked {c.get('component')} and detected {c.get('problem_type')}. I recommend {action} because {c.get('reason')}."
                )
                memory = (plan.get("memory_evidence") or {}).get(
                    "success_rate_for_action"
                )
                if memory is not None:
                    updates.append(
                        f"I compared this with previous decisions. Similar recovery success rate is {memory}."
                    )
                if c.get("requires_human_approval"):
                    updates.append(
                        f"I will not run {action} automatically because this action is risky or has weak historical evidence."
                    )
        else:
            updates = [
                "I checked Kafka topics, consumer state, Postgres, Redis, OpenAI fallback, Airflow reconciliation, MCP context, and recent recovery memory.",
                "No unsafe pipeline stage was detected, so I am not taking recovery action.",
            ]
        return {
            "state": state,
            "badge_color": badge_color,
            "is_active": bool(unhealthy),
            "headline": headline,
            "human_updates": updates,
            "last_memory_samples": latest_memory[:5],
            "uses": [
                "health_signals",
                "logs_and_metrics",
                "rag_memory",
                "mcp_tools",
                "risk_policy",
                "post_action_verification",
            ],
        }

    def _build_stage_map(
        self, components: List[Dict[str, Any]], latest_memory: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        by_component = {c.get("component"): c for c in components}

        def comp_status(name: str) -> Dict[str, Any]:
            return by_component.get(
                name,
                {
                    "status": "healthy",
                    "reason": "No direct health signal currently reports an issue.",
                    "suggested_action": "none",
                },
            )

        def stage(
            stage_id: str,
            label: str,
            component: str,
            description: str,
            agent_relevant: bool = True,
        ) -> Dict[str, Any]:
            c = comp_status(component)
            status = c.get("status", "healthy")
            color = (
                "green"
                if status == "healthy"
                else "yellow" if status in {"degraded", "unknown"} else "red"
            )
            active = status != "healthy" and agent_relevant
            if active and c.get("requires_human_approval"):
                agent_state = "waiting_for_human"
            elif active:
                agent_state = "detecting_planning"
            else:
                agent_state = "sleeping"
            return {
                "id": stage_id,
                "label": label,
                "component": component,
                "description": description,
                "status": status,
                "color": color,
                "agent_state": agent_state,
                "agent_active": active,
                "problem_type": c.get("problem_type", "none"),
                "reason": c.get("reason", "healthy"),
                "suggested_action": c.get("suggested_action", "none"),
                "requires_human_approval": c.get("requires_human_approval", False),
                "agent_plan": c.get("agent_plan"),
            }

        stages = [
            stage(
                "gateway",
                "Producer/API Gateway",
                "control_plane",
                "FastAPI publishes records into Kafka and exposes control-plane APIs.",
            ),
            stage(
                "kafka",
                "Kafka Topics",
                "kafka",
                "raw_orders and dead_letter_events availability.",
            ),
            stage(
                "consumer",
                "Consumer Service",
                "consumer",
                "Consumes events, checks pause state, and drives healing.",
            ),
            stage(
                "rules",
                "Rules Engine",
                "consumer",
                "Fast deterministic fixes before LLM.",
            ),
            stage(
                "rag",
                "RAG Memory",
                "openai",
                "Similar incident retrieval and previous decisions.",
            ),
            stage(
                "agent",
                "LangGraph Agent",
                "openai",
                "Plans recovery and validates safe actions.",
            ),
            stage(
                "mcp",
                "MCP Tool Layer",
                "redis",
                "Standard operational access to Redis, DLQ, incidents, and replay.",
            ),
            stage(
                "approval",
                "Human Approval",
                "consumer",
                "Manual gate for risky recovery actions.",
            ),
            stage(
                "postgres",
                "PostgreSQL Sink",
                "postgres",
                "Orders, incidents, replay audit, and recovery memory.",
            ),
            stage(
                "dlq",
                "DLQ Replay",
                "kafka",
                "Quarantine and replay path for failed events.",
            ),
            stage(
                "airflow",
                "Airflow Reconciliation",
                "airflow",
                "Daily reconciliation and recovery reports.",
            ),
            stage(
                "observability",
                "Metrics and Logs",
                "control_plane",
                "Prometheus metrics, dashboard health, and operational logs.",
            ),
        ]
        return stages

    # ---------- Logging and healing ----------
    def log_detected_problems(
        self, health: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        health = health or self.full_health_check()
        logged = []
        for c in health["components"]:
            if c["status"] == "healthy":
                continue
            incident_id = insert_pipeline_step_incident(
                component=c["component"],
                problem_type=c["problem_type"],
                reason=c["reason"],
                detected_state={
                    "health_signal": c.get("detected_state") or {},
                    "agent_plan": c.get("agent_plan") or {},
                },
                recovery_action=c.get("suggested_action"),
                risk_level=c.get("risk_level") or "medium",
                status="detected",
                requires_human_approval=bool(c.get("requires_human_approval")),
            )
            item = dict(c)
            item["step_incident_id"] = incident_id
            logged.append(item)
        return logged

    def heal_component(
        self, component: str, action: Optional[str] = None, approve_risky: bool = False
    ) -> Dict[str, Any]:
        health = self.full_health_check()
        problems = [
            c
            for c in health["components"]
            if c["component"] == component and c["status"] != "healthy"
        ]
        if not problems:
            self.budget.record_success(component)
            return {
                "component": component,
                "status": "already_healthy",
                "verification": health,
            }
        problem = problems[0]
        plan = problem.get("agent_plan") or {}
        action = (
            action or plan.get("proposed_action") or problem.get("suggested_action")
        )
        requires_approval = bool(
            plan.get("requires_human_approval")
            or problem.get("requires_human_approval")
        )
        if requires_approval and not approve_risky:
            existing = find_pending_approval(component, action)
            if existing:
                return {
                    "component": component,
                    "status": "manual_review",
                    "approval": existing,
                    "action": action,
                    "agent_plan": plan,
                    "already_pending": True,
                }
        if not requires_approval or approve_risky:
            decision = self.budget.check(component)
            if not decision.allowed:
                return self._budget_blocked(component, action, problem, decision)
        incident_id = insert_pipeline_step_incident(
            component=component,
            problem_type=problem.get("problem_type", "unknown"),
            reason=problem.get("reason", ""),
            detected_state={
                "health_signal": problem.get("detected_state") or {},
                "agent_plan": plan,
            },
            recovery_action=action,
            risk_level=problem.get("risk_level") or "medium",
            status="healing_started",
            requires_human_approval=requires_approval,
        )
        if requires_approval and not approve_risky:
            update_pipeline_step_incident(
                incident_id,
                "manual_review",
                action,
                {
                    "approved": False,
                    "agent_plan": plan,
                    "message": "Risky action requires approval",
                },
            )
            approval = create_approval_request(
                component,
                action,
                problem.get("risk_level") or "medium",
                problem.get("reason", "Risky pipeline recovery requires approval"),
                step_incident_id=incident_id,
            )
            send_alert(
                component,
                "warning",
                f"Human approval required for {action}",
                {"step_incident_id": incident_id, "approval": approval},
            )
            remember_recovery(
                component,
                problem.get("problem_type", "unknown"),
                action,
                "manual_review",
                {"agent_plan": plan},
            )
            return {
                "component": component,
                "status": "manual_review",
                "step_incident_id": incident_id,
                "approval": approval,
                "action": action,
                "agent_plan": plan,
            }
        self.budget.record_attempt(component)
        result = self._execute_action(problem, action)
        verify = self.full_health_check()
        still_bad = [
            c
            for c in verify["components"]
            if c["component"] == component and c["status"] != "healthy"
        ]
        final_status = "healed" if not still_bad else "failed"
        if final_status == "healed":
            self.budget.record_success(component)
        update_pipeline_step_incident(
            incident_id,
            final_status,
            action,
            {"action_result": result, "post_check": verify, "agent_plan": plan},
        )
        remember_recovery(
            component,
            problem.get("problem_type", "unknown"),
            action,
            final_status,
            {"action_result": result, "post_check": verify, "agent_plan": plan},
        )
        if final_status == "failed":
            send_alert(
                component,
                "critical",
                f"Pipeline recovery failed for {component}: {action}",
                {"step_incident_id": incident_id, "result": result},
            )
        trace_event(
            "pipeline_recovery",
            component,
            final_status,
            metadata={"action": action, "result": result},
        )
        return {
            "component": component,
            "status": final_status,
            "step_incident_id": incident_id,
            "action": action,
            "result": result,
            "agent_plan": plan,
            "verification": verify,
        }

    def _budget_blocked(
        self, component: str, action: Optional[str], problem: Dict[str, Any], decision
    ) -> Dict[str, Any]:
        """Skip an automatic heal because the component's recovery budget is spent.

        Only the first exhaustion writes an incident and raises an alert; later
        cycles return quietly so a dead component does not spam the log or pager.
        """
        status = "escalated" if decision.status == "exhausted" else "backoff"
        if decision.first_exhaustion:
            message = (
                f"Automatic recovery for {component} gave up after "
                f"{decision.attempts} attempts; a human needs to look at it."
            )
            incident_id = insert_pipeline_step_incident(
                component=component,
                problem_type=problem.get("problem_type", "unknown"),
                reason=message,
                detected_state={"health_signal": problem.get("detected_state") or {}},
                recovery_action=action,
                risk_level=problem.get("risk_level") or "medium",
                status="escalated",
                requires_human_approval=True,
            )
            send_alert(
                component, "critical", message, {"step_incident_id": incident_id}
            )
            remember_recovery(
                component,
                problem.get("problem_type", "unknown"),
                action,
                "failed",
                {"budget": decision.as_dict()},
            )
            trace_event(
                "pipeline_recovery",
                component,
                "escalated",
                metadata={"action": action, "budget": decision.as_dict()},
            )
        return {
            "component": component,
            "status": status,
            "action": action,
            "reason": problem.get("reason"),
            "budget": decision.as_dict(),
        }

    def heal_all_safe(self) -> Dict[str, Any]:
        health = self.full_health_check()
        results = []
        for c in health["components"]:
            if c["status"] == "healthy":
                continue
            if c.get("requires_human_approval"):
                self.log_detected_problems({"components": [c]})
                results.append(
                    {
                        "component": c["component"],
                        "status": "manual_review",
                        "reason": c["reason"],
                        "agent_plan": c.get("agent_plan"),
                    }
                )
                continue
            if AUTO_HEAL_PIPELINE_STEPS:
                results.append(
                    self.heal_component(
                        c["component"], c.get("suggested_action"), approve_risky=False
                    )
                )
            else:
                results.append(
                    {
                        "component": c["component"],
                        "status": "detected_only",
                        "agent_plan": c.get("agent_plan"),
                    }
                )
        return {
            "initial_status": health["overall_status"],
            "results": results,
            "final_health": self.full_health_check(),
        }

    def _execute_action(self, problem: Dict[str, Any], action: str) -> Dict[str, Any]:
        trace_event(
            "pipeline_recovery",
            problem.get("component", "unknown"),
            "action_started",
            metadata={"action": action, "problem": problem},
        )
        if action == "create_missing_topic":
            from src.recovery_adapters.kafka_admin_recovery import ensure_topic

            topic = (problem.get("detected_state") or {}).get("missing_topic")
            if not topic:
                return {
                    "ok": False,
                    "error": "missing topic not found in detected_state",
                }
            return ensure_topic(topic)
        if action == "resume_consumer":
            import redis

            client = redis.Redis(
                host=REDIS_HOST, port=REDIS_PORT, decode_responses=True
            )
            client.set("consumer:paused", "false")
            # Docker recovery is optional and dry-run by default.
            from src.recovery_adapters.docker_recovery import start_service

            docker_result = start_service("consumer")
            return {
                "ok": True,
                "consumer_paused": False,
                "docker_recovery": docker_result,
            }
        if action in {"restart_consumer", "restart_consumer_container"}:
            from src.recovery_adapters.docker_recovery import start_service

            return start_service("consumer")
        if action == "enable_deterministic_fallback":
            import redis

            client = redis.Redis(
                host=REDIS_HOST, port=REDIS_PORT, decode_responses=True
            )
            client.set("llm:fallback_mode", "deterministic")
            return {"ok": True, "fallback_mode": "deterministic"}
        if action == "pause_consumer_and_retry_db":
            try:
                import redis

                client = redis.Redis(
                    host=REDIS_HOST, port=REDIS_PORT, decode_responses=True
                )
                client.set("consumer:paused", "true")
            except Exception:
                pass
            from src.recovery_adapters.docker_recovery import start_service

            return {
                "ok": True,
                "consumer_paused": True,
                "docker_recovery": start_service("postgres"),
                "note": "Paused consumer while database recovers, then verify and resume.",
            }
        if action == "continue_without_retry_memory":
            send_alert(
                "redis",
                "warning",
                "Redis unavailable. Running in degraded retry-memory mode.",
                {"action": action},
            )
            return {"ok": True, "mode": "degraded_no_redis_retry_memory"}
        if action == "restart_redis_container":
            from src.recovery_adapters.docker_recovery import start_service

            result = start_service("redis")
            send_alert(
                "redis",
                "info",
                "Redis restart was attempted by safe auto-heal.",
                {"action": action, "result": result},
            )
            return result
        if action == "run_reconciliation":
            from src.recovery_adapters.airflow_recovery import rerun_reconciliation

            return rerun_reconciliation()
        if action == "restart_airflow_services":
            from src.recovery_adapters.docker_recovery import start_service

            return {
                "webserver": start_service("airflow-webserver"),
                "scheduler": start_service("airflow-scheduler"),
            }
        if action == "restart_control_plane_service":
            from src.recovery_adapters.docker_recovery import start_service

            return {
                "data_api": start_service("data-api"),
                "frontend": start_service("frontend"),
                "metrics": start_service("metrics"),
                "prometheus": start_service("prometheus"),
            }
        if action == "run_safe_migration":
            return {
                "ok": False,
                "requires_operator": True,
                "note": "Apply db/init.sql migration or approve operator migration before retry.",
            }
        if action == "check_consumer_logs":
            from src.recovery_adapters.docker_recovery import service_logs

            logs = service_logs("consumer")
            return {
                "ok": True,
                "log_diagnosis": diagnose_component_logs("consumer", str(logs)),
                "logs": logs,
            }
        if action == "check_control_plane_logs":
            from src.recovery_adapters.docker_recovery import service_logs

            logs = {
                name: service_logs(name)
                for name in ["data-api", "frontend", "metrics", "prometheus"]
            }
            return {
                "ok": True,
                "logs": logs,
                "log_diagnosis": diagnose_component_logs("control_plane", str(logs)),
            }
        return {"ok": False, "error": f"Unsupported action: {action}"}


_agent: Optional[PipelineHealingAgent] = None


def get_pipeline_healing_agent() -> PipelineHealingAgent:
    global _agent
    if _agent is None:
        _agent = PipelineHealingAgent()
    return _agent


def get_pipeline_health() -> Dict[str, Any]:
    return get_pipeline_healing_agent().full_health_check()


def heal_safe_pipeline_steps() -> Dict[str, Any]:
    return get_pipeline_healing_agent().heal_all_safe()


def heal_pipeline_component(
    component: str, action: Optional[str] = None, approve_risky: bool = False
) -> Dict[str, Any]:
    return get_pipeline_healing_agent().heal_component(component, action, approve_risky)


def recent_pipeline_step_incidents(limit: int = 50, status: Optional[str] = None):
    return list_pipeline_step_incidents(limit=limit, status=status)
