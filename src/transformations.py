"""Data transformation utilities for the self healing pipeline.

These transformations are deterministic and safe. They are used by the API,
dashboard, and tests before events are sent to Kafka or replayed from DLQ.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Tuple

STATUS_MAP = {
    "create": "created",
    "created": "created",
    "paid": "paid",
    "pay": "paid",
    "cancel": "cancelled",
    "canceled": "cancelled",
    "cancelled": "cancelled",
    "refund": "refunded",
    "refunded": "refunded",
}


def transform_order_payload(
    payload: Dict[str, Any], default_currency: str = "USD"
) -> Tuple[Dict[str, Any], List[str]]:
    """Return a transformed copy of an order payload and the applied steps.

    The function only performs safe, explainable transformations:
    - trim string fields
    - cast numeric amount strings to float
    - normalize status spelling and case
    - fill a missing currency with a default value
    - add schema_version when missing
    """
    transformed = deepcopy(payload)
    steps: List[str] = []

    for field in ["event_id", "customer_id", "currency", "status"]:
        if isinstance(transformed.get(field), str):
            original = transformed[field]
            transformed[field] = original.strip()
            if transformed[field] != original:
                steps.append(f"trim_{field}")

    if "amount" in transformed and isinstance(transformed["amount"], str):
        amount_text = transformed["amount"].strip().replace(",", "")
        try:
            transformed["amount"] = float(amount_text)
            steps.append("cast_amount_to_float")
        except ValueError:
            steps.append("amount_cast_failed")

    if not transformed.get("currency"):
        transformed["currency"] = default_currency
        steps.append("fill_default_currency")
    elif isinstance(transformed.get("currency"), str):
        upper_currency = transformed["currency"].upper()
        if upper_currency != transformed["currency"]:
            transformed["currency"] = upper_currency
            steps.append("uppercase_currency")

    if isinstance(transformed.get("status"), str):
        normalized_status = transformed["status"].lower().strip()
        mapped_status = STATUS_MAP.get(normalized_status)
        if mapped_status and mapped_status != transformed["status"]:
            transformed["status"] = mapped_status
            steps.append("normalize_status")

    if "schema_version" not in transformed:
        transformed["schema_version"] = 1
        steps.append("add_schema_version")

    return transformed, steps


def transform_many(
    payloads: List[Dict[str, Any]], default_currency: str = "USD"
) -> List[Dict[str, Any]]:
    """Transform a list of payloads and include transformation metadata."""
    output = []
    for payload in payloads:
        transformed, steps = transform_order_payload(
            payload, default_currency=default_currency
        )
        output.append({"original": payload, "transformed": transformed, "steps": steps})
    return output
