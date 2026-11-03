from src.idempotency import payload_fingerprint


def test_payload_fingerprint_is_order_independent():
    left = {"a": 1, "b": 2}
    right = {"b": 2, "a": 1}
    assert payload_fingerprint(left) == payload_fingerprint(right)


def test_payload_fingerprint_changes_when_payload_changes():
    assert payload_fingerprint({"amount": 10}) != payload_fingerprint({"amount": 11})
