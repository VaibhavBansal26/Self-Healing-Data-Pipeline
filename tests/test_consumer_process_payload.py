"""Regression tests for the validation-failure path in consumer.process_payload.

The path used to read ``final_status`` before assignment, raising
UnboundLocalError on every invalid record.
"""

from __future__ import annotations

from unittest import mock

import pytest

import src.consumer as consumer

BAD_PAYLOAD = {
    "event_id": "e1",
    "customer_id": "c1",
    "amount": "29.50",
    "currency": "USD",
    "status": "paid",
}
HEALED_PAYLOAD = dict(BAD_PAYLOAD, amount=29.5)


@pytest.fixture
def harness():
    """Patch every external dependency so only process_payload's logic runs."""
    healed_order = mock.Mock(event_id="e1")
    # First validation (raw payload) fails; second (healed payload) succeeds.
    validate = mock.Mock(
        side_effect=[ValueError("amount should be a valid number"), healed_order]
    )
    patches = {
        "validate": mock.patch.object(consumer, "validate_order_event", validate),
        "explain": mock.patch.object(
            consumer, "explain_validation_error", return_value="amount invalid"
        ),
        "retry_get": mock.patch.object(
            consumer, "safe_get_retry_count", return_value=0
        ),
        "retry_inc": mock.patch.object(consumer, "safe_increment_retry"),
        "journey": mock.patch.object(consumer, "log_event_journey"),
        "insert_order": mock.patch.object(consumer, "insert_order"),
        "record": mock.patch.object(consumer, "record_incident_and_memory"),
        "dlq": mock.patch.object(consumer, "send_to_dlq"),
        "resume": mock.patch.object(
            consumer, "maybe_resume_after_human_interrupt", side_effect=lambda r, t: r
        ),
        "redis": mock.patch.object(consumer, "redis_client"),
        "invoke": mock.patch.object(consumer.healing_graph, "invoke"),
    }
    started = {name: p.start() for name, p in patches.items()}
    yield started
    mock.patch.stopall()


def test_healed_record_is_inserted_and_recorded(harness):
    harness["invoke"].return_value = {
        "decision": {
            "action": "cast_amount_to_float",
            "risk_level": "low",
            "confidence": 0.93,
        },
        "final_status": "healed",
        "healed_payload": HEALED_PAYLOAD,
    }

    consumer.process_payload(dict(BAD_PAYLOAD))

    harness["insert_order"].assert_called_once()
    harness["dlq"].assert_not_called()
    assert harness["record"].call_args.args[6] == "healed"


def test_manual_review_is_recorded_without_dlq(harness):
    harness["invoke"].return_value = {
        "decision": {
            "action": "manual_review",
            "risk_level": "high",
            "confidence": 0.7,
        },
        "final_status": "manual_review",
        "healed_payload": None,
    }

    consumer.process_payload(dict(BAD_PAYLOAD))

    harness["dlq"].assert_not_called()
    harness["insert_order"].assert_not_called()
    assert harness["record"].call_args.args[6] == "manual_review"


def test_failed_repair_goes_to_dlq(harness):
    harness["invoke"].return_value = {
        "decision": {"action": "send_to_dlq", "risk_level": "high"},
        "final_status": "failed",
        "healed_payload": None,
    }

    consumer.process_payload(dict(BAD_PAYLOAD))

    harness["dlq"].assert_called_once()
    harness["insert_order"].assert_not_called()


def test_missing_final_status_defaults_to_failed_and_dlq(harness):
    harness["invoke"].return_value = {"decision": {}}

    consumer.process_payload(dict(BAD_PAYLOAD))

    harness["dlq"].assert_called_once()
    journey_statuses = [
        c.args[4]
        for c in harness["journey"].call_args_list
        if c.args[2] == "agent_decision"
    ]
    assert journey_statuses == ["failed"]
