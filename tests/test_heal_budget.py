from __future__ import annotations

from unittest import mock

import pytest

from src.heal_budget import HealBudget


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds: float):
        self.now += seconds


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def budget(clock):
    return HealBudget(
        max_attempts=3,
        window_seconds=900,
        backoff_base_seconds=10,
        backoff_cap_seconds=60,
        clock=clock,
    )


def test_first_attempt_is_allowed(budget):
    assert budget.check("consumer").allowed


def test_backoff_blocks_immediate_retry_then_allows_it(budget, clock):
    budget.record_attempt("consumer")

    blocked = budget.check("consumer")
    assert (blocked.allowed, blocked.status) == (False, "backoff")
    assert blocked.retry_after_seconds == pytest.approx(10)

    clock.advance(10)
    assert budget.check("consumer").allowed


def test_backoff_doubles_and_is_capped(budget, clock):
    waits = []
    for _ in range(2):
        budget.record_attempt("consumer")
        waits.append(budget.check("consumer").retry_after_seconds)
        clock.advance(waits[-1])
    assert waits == [pytest.approx(10), pytest.approx(20)]


def test_budget_exhausts_after_max_attempts(budget, clock):
    for _ in range(3):
        assert budget.check("consumer").allowed
        budget.record_attempt("consumer")
        clock.advance(100)

    decision = budget.check("consumer")
    assert (decision.allowed, decision.status, decision.attempts) == (
        False,
        "exhausted",
        3,
    )


def test_exhaustion_is_reported_as_first_only_once(budget, clock):
    for _ in range(3):
        budget.record_attempt("consumer")
        clock.advance(100)

    assert budget.check("consumer").first_exhaustion is True
    assert budget.check("consumer").first_exhaustion is False


def test_attempts_expire_with_the_window(budget, clock):
    for _ in range(3):
        budget.record_attempt("consumer")
        clock.advance(100)
    assert budget.check("consumer").status == "exhausted"

    clock.advance(900)
    assert budget.check("consumer").allowed


def test_success_resets_history_and_allows_a_new_alert(budget, clock):
    for _ in range(3):
        budget.record_attempt("consumer")
        clock.advance(100)
    budget.check("consumer")

    budget.record_success("consumer")

    assert budget.check("consumer").allowed
    for _ in range(3):
        budget.record_attempt("consumer")
        clock.advance(100)
    assert budget.check("consumer").first_exhaustion is True


def test_components_have_independent_budgets(budget, clock):
    for _ in range(3):
        budget.record_attempt("consumer")
        clock.advance(100)

    assert budget.check("consumer").status == "exhausted"
    assert budget.check("redis").allowed


def test_from_env_reads_limits(monkeypatch):
    monkeypatch.setenv("HEAL_MAX_ATTEMPTS", "5")
    monkeypatch.setenv("HEAL_WINDOW_SECONDS", "60")

    b = HealBudget.from_env()

    assert (b.max_attempts, b.window_seconds) == (5, 60.0)


# --- wired into the healing agent -------------------------------------------------


@pytest.fixture
def agent(clock):
    from src import pipeline_health as ph

    a = ph.PipelineHealingAgent.__new__(ph.PipelineHealingAgent)
    a.budget = HealBudget(
        max_attempts=3,
        window_seconds=900,
        backoff_base_seconds=10,
        backoff_cap_seconds=60,
        clock=clock,
    )
    unhealthy = {
        "overall_status": "unhealthy",
        "components": [
            {
                "component": "consumer",
                "status": "unhealthy",
                "problem_type": "consumer_container_down",
                "reason": "container exited",
                "risk_level": "medium",
                "suggested_action": "restart_consumer_container",
                "requires_human_approval": False,
                "agent_plan": {"proposed_action": "restart_consumer_container"},
            }
        ],
    }
    a.full_health_check = mock.Mock(return_value=unhealthy)  # restart never fixes it
    a._execute_action = mock.Mock(return_value={"ok": True})
    patches = [
        mock.patch.object(ph, "insert_pipeline_step_incident", return_value=1),
        mock.patch.object(ph, "update_pipeline_step_incident"),
        mock.patch.object(ph, "remember_recovery"),
        mock.patch.object(ph, "send_alert"),
        mock.patch.object(ph, "trace_event"),
    ]
    mocks = [p.start() for p in patches]
    a.alert = mocks[3]
    a.insert_incident = mocks[0]
    yield a
    mock.patch.stopall()


def test_persistently_failing_component_stops_being_restarted(agent, clock):
    statuses = []
    for _ in range(20):  # twenty healer cycles, 8s apart
        statuses.append(agent.heal_component("consumer")["status"])
        clock.advance(8)

    assert agent._execute_action.call_count <= 3
    assert statuses[-1] == "escalated"
    assert "failed" in statuses and "backoff" in statuses


def test_escalation_alerts_and_records_an_incident_only_once(agent, clock):
    for _ in range(40):
        agent.heal_component("consumer")
        clock.advance(8)

    critical = [
        c
        for c in agent.alert.call_args_list
        if c.args[1] == "critical" and "gave up" in c.args[2]
    ]
    assert len(critical) == 1
    escalated_rows = [
        c
        for c in agent.insert_incident.call_args_list
        if c.kwargs.get("status") == "escalated"
    ]
    assert len(escalated_rows) == 1


def test_component_that_recovers_gets_a_fresh_budget(agent, clock):
    healthy = {"overall_status": "healthy", "components": []}
    for _ in range(3):
        agent.heal_component("consumer")
        clock.advance(100)
    assert agent.heal_component("consumer")["status"] == "escalated"

    agent.full_health_check.return_value = healthy
    assert agent.heal_component("consumer")["status"] == "already_healthy"

    assert agent.budget.check("consumer").allowed


# --- protected services --------------------------------------------------------------


@pytest.mark.parametrize("service", ["data-api", "auto-healer", "healing_data_api"])
def test_healer_refuses_to_touch_its_own_services(service, monkeypatch):
    from src import docker_runtime

    monkeypatch.setenv("ENABLE_DOCKER_RECOVERY", "true")
    with mock.patch.object(docker_runtime, "_client") as client:
        for fn in (docker_runtime.start_container, docker_runtime.restart_container):
            result = fn(service)
            assert result["ok"] is False and result["reason"] == "protected_service"
        client.assert_not_called()


def test_other_services_are_not_protected(monkeypatch):
    from src import docker_runtime

    monkeypatch.setenv("ENABLE_DOCKER_RECOVERY", "false")

    assert (
        docker_runtime.start_container("consumer")["reason"]
        == "ENABLE_DOCKER_RECOVERY is not true"
    )


def test_protected_list_is_configurable(monkeypatch):
    from src import docker_runtime

    monkeypatch.setenv("HEALER_PROTECTED_SERVICES", "kafka, consumer")

    assert docker_runtime.protected_services() == {"kafka", "consumer"}


def test_demo_delay_is_off_by_default(monkeypatch):
    import importlib

    from src import auto_healer_loop

    monkeypatch.delenv("AUTO_HEAL_DEMO_DELAY_SECONDS", raising=False)
    reloaded = importlib.reload(auto_healer_loop)

    assert reloaded.DEMO_DELAY_SECONDS == 0
