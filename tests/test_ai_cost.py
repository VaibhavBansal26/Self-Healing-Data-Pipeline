from src.ai_cost import estimate_cost, estimate_tokens


def test_estimate_tokens_positive():
    assert estimate_tokens("hello world") >= 1


def test_estimate_cost_positive_for_tokens():
    assert estimate_cost("gpt-4o-mini", 1000, 500) > 0
