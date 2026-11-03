from src.multi_agent import compare_agents


def test_compare_agents_returns_winner():
    result = compare_agents({"event_id":"e1","customer_id":"c1","amount":"10.5","currency":"USD","status":"paid"}, "amount invalid")
    assert result["winner"]["action"] == "cast_amount_to_float"
    assert len(result["results"]) == 3
