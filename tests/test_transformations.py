from src.transformations import transform_order_payload


def test_transform_order_payload_safe_steps():
    payload = {
        "event_id": "evt_1",
        "customer_id": " cust_1 ",
        "amount": "1,000.50",
        "currency": "usd",
        "status": "PAY",
    }
    transformed, steps = transform_order_payload(payload)

    assert transformed["customer_id"] == "cust_1"
    assert transformed["amount"] == 1000.50
    assert transformed["currency"] == "USD"
    assert transformed["status"] == "paid"
    assert transformed["schema_version"] == 1
    assert "cast_amount_to_float" in steps
    assert "normalize_status" in steps
