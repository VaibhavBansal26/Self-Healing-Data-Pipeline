from src.data_catalog import demo_data_description, demo_order_events


def test_demo_catalog_has_expected_fields():
    catalog = demo_data_description()
    field_names = {field["name"] for field in catalog["fields"]}
    assert {"event_id", "customer_id", "amount", "currency", "status"}.issubset(field_names)


def test_demo_events_cover_valid_and_invalid_cases():
    events = demo_order_events(prefix="test")
    assert len(events) >= 6
    assert any("currency" not in event for event in events)
    assert any(event.get("amount") == -100 for event in events)
