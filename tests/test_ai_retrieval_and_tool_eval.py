from src.retrieval_eval import evaluate_retrieval
from src.tool_use_eval import evaluate_tool_use, select_tool
from src.agent_trajectory import build_agent_trajectory


def test_retrieval_eval_metrics_present():
    result = evaluate_retrieval()
    assert result["cases"] >= 4
    assert "precision_at_1" in result
    assert "hit_rate_at_k" in result


def test_tool_use_eval_accuracy():
    result = evaluate_tool_use()
    assert result["tool_accuracy"] >= 0.8
    assert result["action_accuracy"] >= 0.8


def test_select_tool_for_dlq():
    selected = select_tool("dead letter queue has stuck events", "dlq")
    assert selected["tool"] == "peek_dlq"


def test_agent_trajectory_builds_steps():
    health = {"agent_status":{"state":"detecting_and_planning", "headline":"testing"}, "stage_map":[{"label":"Postgres", "component":"postgres", "color":"red", "problem_type":"connection_failure", "suggested_action":"retry_postgres", "requires_human_approval":False}]}
    trajectory = build_agent_trajectory(health, [])
    assert trajectory["active_stage_count"] == 1
    assert len(trajectory["trajectory_steps"]) >= 3
