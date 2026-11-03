import pytest
from src.schema_registry import validate_order_event, validate_schema_version


def test_schema_version_supported():
    ok, message = validate_schema_version({"schema_version": 1})
    assert ok is True
    assert message == "ok"


def test_schema_version_unsupported():
    ok, message = validate_schema_version({"schema_version": 999})
    assert ok is False
    assert "Unsupported schema_version" in message


def test_validate_order_event_rejects_extra_fields():
    with pytest.raises(Exception):
        validate_order_event({
            "event_id": "e1",
            "customer_id": "c1",
            "amount": 10,
            "currency": "USD",
            "status": "paid",
            "unknown": "field",
        })
