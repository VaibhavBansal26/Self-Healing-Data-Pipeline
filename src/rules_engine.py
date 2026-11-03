from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class RuleDecision:
    action: str
    reason: str
    confidence: float
    risk_level: str
    requires_human_approval: bool

    def as_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
            "confidence": self.confidence,
            "risk_level": self.risk_level,
            "requires_human_approval": self.requires_human_approval,
            "decision_source": "rules_engine",
        }


STATUS_MAP = {
    "create": "created",
    "created": "created",
    "paid": "paid",
    "pay": "paid",
    "cancel": "cancelled",
    "cancelled": "cancelled",
    "refund": "refunded",
    "refunded": "refunded",
}


def decide_repair(payload: Dict[str, Any], error_message: str = "") -> RuleDecision:
    """Deterministic repair policy used before any LLM call.

    Production principle: use cheap, explainable, testable rules first. Only route
    ambiguous cases to vector memory plus LLM reasoning.
    """
    if not payload.get("event_id"):
        return RuleDecision(
            action="send_to_dlq",
            reason="event_id is missing; replay safety and idempotency require a stable identity key.",
            confidence=0.99,
            risk_level="high",
            requires_human_approval=False,
        )

    if not payload.get("customer_id"):
        return RuleDecision(
            action="manual_review",
            reason="customer_id is missing and the system must not invent customer identity.",
            confidence=0.95,
            risk_level="high",
            requires_human_approval=True,
        )

    if "amount" in payload:
        try:
            amount = float(payload.get("amount"))
            if amount < 0:
                return RuleDecision(
                    action="manual_review",
                    reason="negative amount changes financial meaning and requires human review.",
                    confidence=0.98,
                    risk_level="high",
                    requires_human_approval=True,
                )
        except Exception:
            return RuleDecision(
                action="manual_review",
                reason="amount is not parseable as a numeric value.",
                confidence=0.90,
                risk_level="high",
                requires_human_approval=True,
            )

    if isinstance(payload.get("amount"), str):
        return RuleDecision(
            action="cast_amount_to_float",
            reason="amount is a numeric string, so casting preserves the value while fixing the schema type.",
            confidence=0.93,
            risk_level="low",
            requires_human_approval=False,
        )

    if "currency" not in payload or payload.get("currency") in {None, ""}:
        return RuleDecision(
            action="fill_default_currency",
            reason="currency is missing and policy allows USD as the ecommerce demo default.",
            confidence=0.94,
            risk_level="low",
            requires_human_approval=False,
        )

    status = str(payload.get("status", "")).strip().lower()
    if status in STATUS_MAP and payload.get("status") != STATUS_MAP[status]:
        return RuleDecision(
            action="normalize_status",
            reason="status is a clear spelling or case variant and maps to an allowed enum.",
            confidence=0.92,
            risk_level="low",
            requires_human_approval=False,
        )

    return RuleDecision(
        action="manual_review",
        reason="No deterministic rule safely repairs this validation failure; route to LLM or review.",
        confidence=0.70,
        risk_level="medium",
        requires_human_approval=True,
    )


def apply_repair_action(payload: Dict[str, Any], action: str) -> Tuple[Optional[Dict[str, Any]], str]:
    repaired = dict(payload)
    if action == "cast_amount_to_float":
        repaired["amount"] = float(repaired["amount"])
        return repaired, "amount cast to float"
    if action == "fill_default_currency":
        repaired["currency"] = "USD"
        return repaired, "currency defaulted to USD"
    if action == "normalize_status":
        status = str(repaired.get("status", "")).strip().lower()
        if status not in STATUS_MAP:
            return None, "status was not a known safe variant"
        repaired["status"] = STATUS_MAP[status]
        return repaired, "status normalized to allowed enum"
    return None, f"action {action} does not produce a repaired payload"
