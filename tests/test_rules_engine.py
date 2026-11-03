from src.rules_engine import decide_repair, apply_repair_action


def test_rules_engine_casts_numeric_string_amount():
    payload = {
        "event_id": "e1",
        "customer_id": "c1",
        "amount": "12.50",
        "currency": "USD",
        "status": "paid",
    }
    decision = decide_repair(payload).as_dict()
    assert decision["action"] == "cast_amount_to_float"
    repaired, reason = apply_repair_action(payload, decision["action"])
    assert repaired["amount"] == 12.50
    assert "cast" in reason


def test_rules_engine_missing_customer_goes_to_manual_review():
    payload = {"event_id": "e1", "amount": 12.5, "currency": "USD", "status": "paid"}
    decision = decide_repair(payload).as_dict()
    assert decision["action"] == "manual_review"
    assert decision["requires_human_approval"] is True


def test_rules_engine_missing_event_id_goes_to_dlq():
    payload = {"customer_id": "c1", "amount": 12.5, "currency": "USD", "status": "paid"}
    decision = decide_repair(payload).as_dict()
    assert decision["action"] == "send_to_dlq"
