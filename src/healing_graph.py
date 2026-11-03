from __future__ import annotations

import os
from typing import Dict, Any, Optional
from pydantic import ValidationError
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt
from src.schemas import OrderEvent, HealingDecision
from src.mcp_layer.tool_client import call_pipeline_tool
from src.guardrails import enforce_decision_policy
from src.security import redact_payload
from src.rules_engine import decide_repair, apply_repair_action
from src.llm_safety import should_call_llm, record_llm_failure, sanitize_llm_context
from src.ai_cost import estimate_tokens, record_llm_cost
from src.langsmith_observability import trace_run


def _build_llm() -> Optional[Any]:
    """Create the OpenAI client only when a key exists.

    This lets the project run in deterministic demo mode without crashing the
    consumer. When OPENAI_API_KEY is set, OpenAI is used for ambiguous cases.
    """
    if not os.getenv("OPENAI_API_KEY"):
        return None
    try:
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0)
        return llm.with_structured_output(HealingDecision)
    except Exception as exc:
        print(f"OpenAI client unavailable. Falling back to rule based agent: {exc}")
        return None


structured_llm = _build_llm()


def _redis_client():
    try:
        import redis
        from src.config import REDIS_HOST, REDIS_PORT
        return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    except Exception:
        return None


def retrieve_memory(state: Dict[str, Any]) -> Dict[str, Any]:
    try:
        similar = call_pipeline_tool(
            "search_similar_incidents",
            payload=state["original_payload"],
            error_message=state["error_message"],
            k=3,
        )
    except Exception as exc:
        similar = [{"status": "memory_unavailable", "error": str(exc)}]
    state["similar_incidents"] = similar
    state.setdefault("agent_trace", []).append({
        "step": "RAG retrieve",
        "reason": "Look up similar historic incidents before choosing an action.",
        "evidence_count": len(similar) if isinstance(similar, list) else 0,
        "act": "search_similar_incidents",
    })
    return state


def _rule_based_decision(payload: Dict[str, Any], error_message: str) -> Dict[str, Any]:
    """Compatibility wrapper around the deterministic rules engine."""
    return decide_repair(payload, error_message).as_dict()

def diagnose_error(state: Dict[str, Any]) -> Dict[str, Any]:
    payload = state["original_payload"]
    error_message = state["error_message"]
    similar_incidents = state.get("similar_incidents", [])

    # First use deterministic reason and act logic. It makes the demo reliable
    # and avoids unnecessary LLM calls for obvious repairs.
    decision = _rule_based_decision(payload, error_message)

    # Use OpenAI only for ambiguous medium risk cases when a key exists and the
    # Redis backed rate limiter/circuit breaker allows it.
    llm_gate = should_call_llm(_redis_client())
    if structured_llm is not None and decision["action"] == "manual_review" and decision["risk_level"] == "medium" and llm_gate.allowed:
        redacted_payload = redact_payload(sanitize_llm_context(payload))
        prompt = f"""
You are a data reliability agent for a Kafka streaming pipeline.
The record failed validation.

Redacted, schema relevant payload:
{redacted_payload}

Error:
{error_message}

Similar previous incidents from vector memory:
{similar_incidents}

Choose exactly one safe action:
1. cast_amount_to_float
2. fill_default_currency
3. normalize_status
4. send_to_dlq
5. manual_review

Rules:
- Do not invent event_id or customer_id.
- Only fill currency if missing, using USD.
- Only normalize status when it is a clear spelling or case issue.
- Send to DLQ if amount is negative or event_id is missing.
- Route missing customer_id or financial ambiguity to manual_review.
"""
        try:
            with trace_run("healing_graph.diagnose_error", inputs={"payload": redacted_payload, "error_message": error_message}, metadata={"event_id": payload.get("event_id"), "agent": "langgraph_healing_agent"}):
                decision = structured_llm.invoke(prompt).model_dump()
            prompt_tokens = estimate_tokens(prompt)
            completion_tokens = estimate_tokens(decision)
            model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            cost = record_llm_cost(
                event_id=str(payload.get("event_id", "unknown")),
                model=model_name,
                agent_name="langgraph_healing_agent",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                status="success",
            )
            state["llm_cost"] = cost.__dict__
            decision["reason"] = f"OpenAI decision: {decision.get('reason', '')}"
        except Exception as exc:
            record_llm_failure(_redis_client())
            record_llm_cost(
                event_id=str(payload.get("event_id", "unknown")),
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                agent_name="langgraph_healing_agent",
                prompt_tokens=estimate_tokens(locals().get("prompt", "")),
                completion_tokens=0,
                status="failed",
            )
            decision = {
                "action": "manual_review",
                "reason": f"LLM unavailable or invalid structured output: {exc}",
                "confidence": 0.0,
                "risk_level": "high",
                "requires_human_approval": True,
                "decision_source": "llm_fallback",
            }
    elif not llm_gate.allowed and decision["risk_level"] == "medium":
        decision["reason"] = f"{decision['reason']} LLM skipped: {llm_gate.reason}"

    # Guardrails can still override the action.
    state["decision"] = enforce_decision_policy(decision, payload, similar_incidents)
    state.setdefault("agent_trace", []).append({
        "step": "Reason",
        "reason": state["decision"].get("reason"),
        "act": state["decision"].get("action"),
        "risk_level": state["decision"].get("risk_level"),
        "confidence": state["decision"].get("confidence"),
    })
    return state


def human_approval_gate(state: Dict[str, Any]) -> Dict[str, Any]:
    decision = state.get("decision") or {}
    requires_approval = decision.get("requires_human_approval", False)
    risk_level = decision.get("risk_level")

    if not requires_approval and risk_level != "high":
        state.setdefault("agent_trace", []).append({
            "step": "Risk gate",
            "reason": "Low risk repair does not require human approval.",
            "act": "continue_to_repair",
        })
        return state

    approval = interrupt(
        {
            "message": "Human approval required before this record can be repaired.",
            "payload": redact_payload(state["original_payload"]),
            "error_message": state["error_message"],
            "decision": decision,
            "similar_incidents": state.get("similar_incidents", []),
            "expected_response": {"approved": True, "notes": "optional reviewer notes"},
        }
    )

    state["human_feedback"] = approval
    if not approval or not approval.get("approved"):
        state["final_status"] = "manual_review"
        state.setdefault("agent_trace", []).append({
            "step": "Human approval",
            "reason": "Repair is high risk or needs reviewer approval; terminal approval is disabled in Docker demo.",
            "act": "route_to_manual_review",
        })
    else:
        state.setdefault("agent_trace", []).append({
            "step": "Human approval",
            "reason": approval.get("notes", "approved"),
            "act": "approved_continue_to_repair",
        })
    return state


def repair_payload(state: Dict[str, Any]) -> Dict[str, Any]:
    if state.get("final_status") == "manual_review":
        return state

    payload = dict(state["original_payload"])
    decision = state.get("decision") or {}
    action = decision.get("action")

    healed_payload, repair_reason = apply_repair_action(payload, action)
    if healed_payload is not None:
        state["healed_payload"] = healed_payload
        state["final_status"] = "repair_attempted"
    elif action == "manual_review":
        state["final_status"] = "manual_review"
    else:
        state["final_status"] = "failed"

    state.setdefault("agent_trace", []).append({
        "step": "Act",
        "reason": repair_reason,
        "act": action,
        "healed_payload": state.get("healed_payload"),
        "status": state.get("final_status"),
    })
    return state

def verify_payload(state: Dict[str, Any]) -> Dict[str, Any]:
    healed_payload = state.get("healed_payload")
    if not healed_payload:
        state["verified"] = False
        return state

    try:
        OrderEvent(**healed_payload)
        state["verified"] = True
        state["final_status"] = "healed"
        reason = "Repaired payload passed schema and business validation."
    except ValidationError as exc:
        state["verified"] = False
        state["final_status"] = "failed"
        reason = f"Repaired payload failed validation: {exc}"
    state.setdefault("agent_trace", []).append({
        "step": "Verify",
        "reason": reason,
        "act": "validate_repaired_payload",
        "verified": state["verified"],
        "status": state["final_status"],
    })
    return state


def route_after_repair(state: Dict[str, Any]) -> str:
    if state.get("final_status") == "repair_attempted":
        return "verify_payload"
    return END


def build_healing_graph():
    graph = StateGraph(dict)
    graph.add_node("retrieve_memory", retrieve_memory)
    graph.add_node("diagnose_error", diagnose_error)
    graph.add_node("human_approval_gate", human_approval_gate)
    graph.add_node("repair_payload", repair_payload)
    graph.add_node("verify_payload", verify_payload)

    graph.set_entry_point("retrieve_memory")
    graph.add_edge("retrieve_memory", "diagnose_error")
    graph.add_edge("diagnose_error", "human_approval_gate")
    graph.add_edge("human_approval_gate", "repair_payload")
    graph.add_conditional_edges("repair_payload", route_after_repair, {"verify_payload": "verify_payload", END: END})
    graph.add_edge("verify_payload", END)
    return graph.compile(checkpointer=MemorySaver())


healing_graph = build_healing_graph()
