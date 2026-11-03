from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any, Dict
from pydantic import ValidationError

from src.guardrails import enforce_decision_policy
from src.rules_engine import decide_repair, apply_repair_action
from src.schemas import OrderEvent
from src.security import redact_payload
from src.ai_cost import estimate_tokens, estimate_cost


@dataclass
class AgentResult:
    agent_name: str
    action: str
    reason: str
    confidence: float
    risk_level: str
    requires_human_approval: bool
    verified: bool
    final_status: str
    healed_payload: Dict[str, Any] | None
    latency_ms: float
    estimated_tokens: int
    estimated_cost_usd: float


def _verify(payload: Dict[str, Any] | None) -> bool:
    if not payload:
        return False
    try:
        OrderEvent(**payload)
        return True
    except ValidationError:
        return False


def detector_agent(payload: Dict[str, Any], error_message: str) -> Dict[str, Any]:
    missing = [
        k
        for k in ["event_id", "customer_id", "amount", "currency", "status"]
        if k not in payload or payload.get(k) in (None, "")
    ]
    return {
        "agent": "detector",
        "missing_fields": missing,
        "has_negative_amount": isinstance(payload.get("amount"), (int, float))
        and payload.get("amount") < 0,
        "schema_relevant_payload": redact_payload(payload),
        "error_message": error_message,
    }


def rules_repair_agent(payload: Dict[str, Any], error_message: str) -> AgentResult:
    started = time.perf_counter()
    decision = decide_repair(payload, error_message).as_dict()
    decision = enforce_decision_policy(decision, payload, [])
    healed, reason = apply_repair_action(payload, decision["action"])
    verified = _verify(healed)
    status = (
        "healed"
        if verified
        else ("manual_review" if decision["action"] == "manual_review" else "failed")
    )
    tokens = estimate_tokens(
        {"payload": payload, "error": error_message, "decision": decision}
    )
    return AgentResult(
        agent_name="rules_repair_agent",
        action=decision["action"],
        reason=reason or decision.get("reason", ""),
        confidence=float(decision.get("confidence", 0.0)),
        risk_level=decision.get("risk_level", "unknown"),
        requires_human_approval=bool(decision.get("requires_human_approval", False)),
        verified=verified,
        final_status=status,
        healed_payload=healed,
        latency_ms=round((time.perf_counter() - started) * 1000, 2),
        estimated_tokens=tokens,
        estimated_cost_usd=0.0,
    )


def conservative_reviewer_agent(
    payload: Dict[str, Any], error_message: str
) -> AgentResult:
    started = time.perf_counter()
    detector = detector_agent(payload, error_message)
    risky = detector["missing_fields"] or detector["has_negative_amount"]
    action = "manual_review" if risky else "send_to_dlq"
    tokens = estimate_tokens(
        {"payload": payload, "error": error_message, "detector": detector}
    )
    return AgentResult(
        agent_name="conservative_reviewer_agent",
        action=action,
        reason="Conservative reviewer routes incomplete or risky records to manual review, otherwise quarantines.",
        confidence=0.85,
        risk_level="high" if risky else "medium",
        requires_human_approval=True,
        verified=False,
        final_status="manual_review" if action == "manual_review" else "failed",
        healed_payload=None,
        latency_ms=round((time.perf_counter() - started) * 1000, 2),
        estimated_tokens=tokens,
        estimated_cost_usd=0.0,
    )


def llm_planner_proxy_agent(
    payload: Dict[str, Any], error_message: str, model: str = "gpt-4o-mini"
) -> AgentResult:
    """Measurable LLM proxy for offline comparison.

    It estimates what an LLM planner would cost and uses the same policy surface.
    Production LLM calls still happen in healing_graph.py when configured.
    """
    started = time.perf_counter()
    decision = decide_repair(payload, error_message).as_dict()
    if decision["action"] == "manual_review" and decision.get("risk_level") == "medium":
        decision["reason"] = (
            "LLM planner proxy would inspect similar incidents, but keeps medium ambiguity in manual review offline."
        )
    prompt_tokens = estimate_tokens(
        {
            "payload": redact_payload(payload),
            "error": error_message,
            "task": "choose safe repair",
        }
    )
    completion_tokens = estimate_tokens(decision)
    healed, reason = apply_repair_action(payload, decision["action"])
    verified = _verify(healed)
    return AgentResult(
        agent_name="llm_planner_proxy_agent",
        action=decision["action"],
        reason=reason or decision.get("reason", ""),
        confidence=float(decision.get("confidence", 0.0)),
        risk_level=decision.get("risk_level", "medium"),
        requires_human_approval=bool(decision.get("requires_human_approval", False)),
        verified=verified,
        final_status=(
            "healed"
            if verified
            else (
                "manual_review" if decision["action"] == "manual_review" else "failed"
            )
        ),
        healed_payload=healed,
        latency_ms=round((time.perf_counter() - started) * 1000, 2),
        estimated_tokens=prompt_tokens + completion_tokens,
        estimated_cost_usd=estimate_cost(model, prompt_tokens, completion_tokens),
    )


def compare_agents(
    payload: Dict[str, Any], error_message: str = "validation failed"
) -> Dict[str, Any]:
    detector = detector_agent(payload, error_message)
    results = [
        rules_repair_agent(payload, error_message),
        conservative_reviewer_agent(payload, error_message),
        llm_planner_proxy_agent(payload, error_message),
    ]
    ranked = sorted(
        results,
        key=lambda r: (
            not r.verified,
            r.requires_human_approval,
            r.estimated_cost_usd,
            r.latency_ms,
        ),
    )
    winner = ranked[0]
    return {
        "detector": detector,
        "results": [asdict(r) for r in results],
        "winner": asdict(winner),
        "selection_policy": "Prefer verified safe repair, then no human approval, then lower cost, then lower latency.",
    }
