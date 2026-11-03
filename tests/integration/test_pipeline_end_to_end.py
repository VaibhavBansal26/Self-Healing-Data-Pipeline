"""End-to-end behaviour of the consumer against real Kafka, Postgres and Redis."""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.usefixtures("running_consumer")


def _event(**overrides):
    event = {
        "event_id": f"evt-{uuid.uuid4().hex[:10]}",
        "customer_id": "cust-1",
        "amount": 29.5,
        "currency": "USD",
        "status": "paid",
    }
    event.update(overrides)
    return {k: v for k, v in event.items() if v is not None}


def _order(h, event_id):
    return h.query(
        "SELECT amount, currency, status FROM orders WHERE event_id=%s", (event_id,)
    )


def _incident_statuses(h, event_id):
    return [
        r[0]
        for r in h.query(
            "SELECT status FROM pipeline_incidents WHERE event_id=%s", (event_id,)
        )
    ]


def test_valid_event_is_inserted(h):
    event = _event()
    h.publish(event)

    rows = h.wait_for(lambda: _order(h, event["event_id"]))

    assert rows and float(rows[0][0]) == 29.5


def test_missing_currency_is_healed_and_recorded(h):
    event = _event(currency=None)
    h.publish(event)

    rows = h.wait_for(lambda: _order(h, event["event_id"]))

    assert rows, "healed record never reached orders"
    assert rows[0][1] == "USD"
    assert h.wait_for(lambda: "healed" in _incident_statuses(h, event["event_id"]))


def test_missing_event_id_goes_to_dlq_not_orders(h):
    event = _event(event_id=None)
    marker = f"cust-{uuid.uuid4().hex[:8]}"
    event["customer_id"] = marker
    h.publish(event)

    messages = h.dlq_messages(lambda m: m["payload"].get("customer_id") == marker)

    assert any(m["payload"].get("customer_id") == marker for m in messages)
    assert h.query("SELECT 1 FROM orders WHERE customer_id=%s", (marker,)) == []


def test_negative_amount_is_routed_to_manual_review(h):
    event = _event(amount=-5.0)
    h.publish(event)

    assert h.wait_for(
        lambda: "manual_review" in _incident_statuses(h, event["event_id"])
    )
    assert _order(h, event["event_id"]) == []


def test_duplicate_event_creates_one_order(h):
    event = _event()
    h.publish(event)
    h.publish(event)

    assert h.wait_for(lambda: _order(h, event["event_id"]))
    h.wait_for(lambda: False, timeout=5)  # give the duplicate time to be processed
    assert len(_order(h, event["event_id"])) == 1


def test_same_event_id_with_different_content_is_rejected(h):
    first = _event(amount=10.0)
    h.publish(first)
    assert h.wait_for(lambda: _order(h, first["event_id"]))

    conflicting = dict(first, amount=999.0)
    h.publish(conflicting)

    assert h.wait_for(lambda: "failed" in _incident_statuses(h, first["event_id"]))
    rows = _order(h, first["event_id"])
    assert len(rows) == 1 and float(rows[0][0]) == 10.0
