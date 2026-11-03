from src.semantic_cache import seed_demo_cache, find_cached_decision, semantic_cache_summary


def test_semantic_cache_returns_similar_verified_decision():
    seed_demo_cache()
    hit = find_cached_decision({"event_id":"x", "customer_id":"c", "amount":"30.0", "currency":"USD", "status":"paid"}, "amount should be a valid number", threshold=0.80)
    assert hit is not None
    assert hit["decision"]["action"] == "cast_amount_to_float"


def test_semantic_cache_summary_has_entries():
    summary = semantic_cache_summary()
    assert summary["entries"] >= 1
