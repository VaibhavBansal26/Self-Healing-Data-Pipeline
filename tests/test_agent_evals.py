from src.agent_evals import evaluate_agents


def test_evaluate_agents_has_cases():
    result = evaluate_agents()
    assert result["cases"] >= 1
    assert "by_agent" in result
