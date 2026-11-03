from __future__ import annotations

from typing import Any, Dict, List
from src.config import LLM_CONFIDENCE_THRESHOLD


def _is_numeric_string(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        float(value)
        return True
    except Exception:
        return False


def similar_incidents_conflict(similar_incidents: List[Dict[str, Any]]) -> bool:
    statuses = {str(item.get("status")) for item in similar_incidents if item.get("status")}
    return "failed" in statuses and "healed" in statuses


def enforce_decision_policy(decision: Dict[str, Any], payload: Dict[str, Any], similar_incidents: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Apply deterministic safety rules after the agent chooses a repair action."""
    decision = dict(decision or {})
    action = decision.get("action", "manual_review")
    confidence = float(decision.get("confidence") or 0)

    high_risk_reasons = []
    if confidence < LLM_CONFIDENCE_THRESHOLD:
        high_risk_reasons.append(f"confidence below {LLM_CONFIDENCE_THRESHOLD}")

    # Casting a numeric string like "29.50" to 29.50 is safe because value is preserved.
    if action == "cast_amount_to_float" and not _is_numeric_string(payload.get("amount")):
        high_risk_reasons.append("amount is not a clean numeric string")

    if payload.get("event_id") in {None, ""}:
        decision["action"] = "send_to_dlq"
        decision["risk_level"] = "high"
        decision["requires_human_approval"] = False
        decision["reason"] = f"{decision.get('reason', '')} Guardrail: missing event_id cannot be replayed safely.".strip()
        return decision

    if payload.get("customer_id") in {None, ""}:
        decision["action"] = "manual_review"
        high_risk_reasons.append("missing customer_id cannot be invented")

    try:
        if float(payload.get("amount", 0)) < 0:
            decision["action"] = "manual_review"
            high_risk_reasons.append("negative amount requires human financial review")
    except Exception:
        pass

    if similar_incidents_conflict(similar_incidents):
        high_risk_reasons.append("similar incident memory has mixed outcomes")

    if high_risk_reasons:
        decision["risk_level"] = "high"
        decision["requires_human_approval"] = True
        decision["reason"] = f"{decision.get('reason', '')} Guardrail: {', '.join(high_risk_reasons)}".strip()
    else:
        decision.setdefault("risk_level", "low")
        decision.setdefault("requires_human_approval", False)

    if decision.get("action") == "send_to_dlq":
        decision["requires_human_approval"] = False
    if decision.get("action") == "manual_review":
        decision["requires_human_approval"] = True
    return decision
