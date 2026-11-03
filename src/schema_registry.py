from __future__ import annotations

from typing import Any, Dict, Tuple
from pydantic import ValidationError
from src.schemas import OrderEvent

SUPPORTED_SCHEMA_VERSIONS = {1, 2}

STATUS_MAP = {
    "pay": "paid",
    "paid": "paid",
    "paid ": "paid",
    "created": "created",
    "create": "created",
    "cancel": "cancelled",
    "cancelled": "cancelled",
    "refund": "refunded",
    "refunded": "refunded",
}


def normalize_schema(payload: Dict[str, Any]) -> tuple[Dict[str, Any], list[str]]:
    """Normalize supported schema versions into the sink contract used by OrderEvent.

    v1: event_id, customer_id, amount, currency, status, schema_version
    v2: event_id, customer_id, amount_cents, currency, order_state, schema_version
    """
    normalized = dict(payload)
    steps: list[str] = []
    version = int(normalized.get("schema_version", 1))
    if version == 2:
        if "amount" not in normalized and "amount_cents" in normalized:
            normalized["amount"] = float(normalized["amount_cents"]) / 100.0
            steps.append("schema_v2.amount_cents_to_amount")
        if "status" not in normalized and "order_state" in normalized:
            normalized["status"] = STATUS_MAP.get(
                str(normalized["order_state"]).lower().strip(),
                str(normalized["order_state"]).lower().strip(),
            )
            steps.append("schema_v2.order_state_to_status")
        normalized.pop("amount_cents", None)
        normalized.pop("order_state", None)
        # Store normalized records in sink contract while preserving incoming version.
        normalized["schema_version"] = 1
    return normalized, steps


def validate_schema_version(payload: Dict[str, Any]) -> Tuple[bool, str]:
    try:
        version = int(payload.get("schema_version", 1))
    except Exception:
        return False, "schema_version must be an integer"
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        return (
            False,
            f"Unsupported schema_version={version}. Supported versions={sorted(SUPPORTED_SCHEMA_VERSIONS)}",
        )
    return True, "ok"


def validate_order_event(payload: Dict[str, Any]) -> OrderEvent:
    ok, message = validate_schema_version(payload)
    if not ok:
        raise ValueError(message)
    normalized, _ = normalize_schema(payload)
    return OrderEvent(**normalized)


def explain_validation_error(payload: Dict[str, Any], exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        return str(exc)
    return f"Schema validation failed: {exc}"
