from src.security import redact_payload


def test_redact_payload_masks_pii():
    payload = {"event_id": "e1", "email": "user@example.com", "amount": 10}
    redacted = redact_payload(payload)
    assert redacted["email"] == "***MASKED***"
    assert redacted["event_id"] == "e1"
