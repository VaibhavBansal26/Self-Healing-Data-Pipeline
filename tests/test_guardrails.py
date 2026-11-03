from src.guardrails import enforce_decision_policy


def test_guardrails_require_human_approval_for_low_confidence():
    decision = {
        "action": "fill_default_currency",
        "reason": "currency missing",
        "confidence": 0.5,
        "risk_level": "low",
        "requires_human_approval": False,
    }
    result = enforce_decision_policy(decision, {"event_id": "e1", "customer_id": "c1"}, [])
    assert result["risk_level"] == "high"
    assert result["requires_human_approval"] is True


def test_guardrails_allow_numeric_string_cast_without_human_approval():
    decision = {
        "action": "cast_amount_to_float",
        "reason": "amount is string",
        "confidence": 0.95,
        "risk_level": "low",
        "requires_human_approval": False,
    }
    result = enforce_decision_policy(decision, {"event_id": "e1", "customer_id": "c1", "amount": "10.00"}, [])
    assert result["risk_level"] == "low"
    assert result["requires_human_approval"] is False
