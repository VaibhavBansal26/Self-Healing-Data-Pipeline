from src.data_catalog import DEMO_SCENARIOS, build_demo_event, demo_data_description


def test_demo_catalog_exposes_scenarios():
    catalog = demo_data_description()
    assert "scenarios" in catalog
    assert "amount_string" in catalog["scenarios"]
    assert set(DEMO_SCENARIOS).issuperset(
        {"valid_order", "negative_amount", "missing_customer"}
    )


def test_build_demo_event_amount_string():
    event = build_demo_event("amount_string", prefix="test")
    assert event["event_id"].startswith("test_amount_string_")
    assert isinstance(event["amount"], str)
    assert event["currency"] == "usd"


def test_duplicate_conflict_events_share_id_but_different_amounts():
    first = build_demo_event("duplicate_conflict_base")
    second = build_demo_event("duplicate_conflict_changed")
    assert first["event_id"] == second["event_id"]
    assert first["amount"] != second["amount"]
