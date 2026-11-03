"""Synthetic demo data catalog for the self healing pipeline."""

from __future__ import annotations

from typing import Any, Dict, List
from uuid import uuid4
import random


DEMO_SCENARIOS = [
    "valid_order",
    "amount_string",
    "missing_currency",
    "bad_status",
    "negative_amount",
    "missing_customer",
    "duplicate_conflict_base",
    "duplicate_conflict_changed",
    "missing_event_id",
    "schema_v2_order",
    "unsupported_schema",
]


def build_demo_event(scenario: str = "valid_order", prefix: str = "ui") -> Dict[str, Any]:
    suffix = uuid4().hex[:8]
    event_id = f"{prefix}_{scenario}_{suffix}"

    if scenario == "valid_order":
        return {"event_id": event_id, "customer_id": "cust_1", "amount": 49.99, "currency": "USD", "status": "paid", "schema_version": 1}
    if scenario == "amount_string":
        return {"event_id": event_id, "customer_id": "cust_2", "amount": "29.50", "currency": "usd", "status": "paid", "schema_version": 1}
    if scenario == "missing_currency":
        return {"event_id": event_id, "customer_id": "cust_3", "amount": 19.99, "status": "created", "schema_version": 1}
    if scenario == "bad_status":
        return {"event_id": event_id, "customer_id": "cust_4", "amount": 10.0, "currency": "USD", "status": "PAY", "schema_version": 1}
    if scenario == "negative_amount":
        return {"event_id": event_id, "customer_id": "cust_5", "amount": -100, "currency": "USD", "status": "paid", "schema_version": 1}
    if scenario == "missing_customer":
        return {"event_id": event_id, "amount": 200, "currency": "USD", "status": "paid", "schema_version": 1}
    if scenario == "missing_event_id":
        return {"customer_id": "cust_missing_event", "amount": 55.25, "currency": "USD", "status": "paid", "schema_version": 1}
    if scenario == "schema_v2_order":
        return {"event_id": event_id, "customer_id": "cust_v2", "amount_cents": 4999, "currency": "USD", "order_state": "PAID", "schema_version": 2}
    if scenario == "unsupported_schema":
        return {"event_id": event_id, "customer_id": "cust_bad_schema", "amount": 12.0, "currency": "USD", "status": "paid", "schema_version": 99}
    if scenario == "duplicate_conflict_base":
        return {"event_id": "ui_duplicate_conflict", "customer_id": "cust_dup", "amount": 75.00, "currency": "USD", "status": "paid", "schema_version": 1}
    if scenario == "duplicate_conflict_changed":
        return {"event_id": "ui_duplicate_conflict", "customer_id": "cust_dup", "amount": 88.00, "currency": "USD", "status": "paid", "schema_version": 1}
    raise ValueError(f"Unsupported demo scenario: {scenario}")


def demo_order_events(prefix: str = "demo") -> List[Dict[str, Any]]:
    return [
        build_demo_event("valid_order", prefix=prefix),
        build_demo_event("amount_string", prefix=prefix),
        build_demo_event("missing_currency", prefix=prefix),
        build_demo_event("bad_status", prefix=prefix),
        build_demo_event("negative_amount", prefix=prefix),
        build_demo_event("missing_customer", prefix=prefix),
        build_demo_event("missing_event_id", prefix=prefix),
        build_demo_event("schema_v2_order", prefix=prefix),
        build_demo_event("unsupported_schema", prefix=prefix),
    ]


def pressure_test_events(total: int = 1000, prefix: str = "pressure") -> List[Dict[str, Any]]:
    """Generate a mixed pressure test dataset.

    Approximate distribution:
    45 percent valid, 35 percent auto healable, 15 percent manual review, 5 percent DLQ.
    """
    total = max(1, min(int(total), 100000))
    weighted = (
        ["valid_order"] * 45
        + ["amount_string"] * 12
        + ["missing_currency"] * 12
        + ["bad_status"] * 11
        + ["negative_amount"] * 10
        + ["missing_customer"] * 5
        + ["missing_event_id"] * 5
        + ["schema_v2_order"] * 8
        + ["unsupported_schema"] * 2
    )
    return [build_demo_event(random.choice(weighted), prefix=f"{prefix}{i}") for i in range(total)]


def demo_data_description() -> Dict[str, Any]:
    return {
        "dataset": "Synthetic ecommerce order events",
        "source_topic": "raw_orders",
        "sink_table": "orders",
        "dlq_topic": "dead_letter_events",
        "scenarios": DEMO_SCENARIOS,
        "fields": [
            {"name": "event_id", "type": "string", "required": True, "description": "Unique idempotency key"},
            {"name": "customer_id", "type": "string", "required": True, "description": "Customer identifier"},
            {"name": "amount", "type": "float", "required": True, "description": "Positive order amount"},
            {"name": "currency", "type": "string", "required": True, "description": "Currency code, default USD for safe repairs"},
            {"name": "status", "type": "enum", "required": True, "description": "created, paid, cancelled, or refunded"},
            {"name": "schema_version", "type": "integer", "required": False, "description": "Schema contract version"},
        ],
        "failure_scenarios": [
            "amount provided as numeric string, healed by agent",
            "missing currency, healed by agent",
            "status spelling or case mismatch, healed by agent",
            "negative amount, routed to human approval",
            "missing customer_id, routed to human approval",
            "missing event_id, sent to DLQ",
            "duplicate event_id with different payload hash, sent to DLQ",
        ],
    }
