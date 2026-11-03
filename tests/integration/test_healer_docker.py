"""The healer acting on real Docker containers.

A throwaway container plays the "consumer" service. Everything between the
health check and the container (health check, budget, action, verification,
incident and alert rows) is the production code path; only the container name
lookup is redirected so the tests never touch a real ``healing_*`` stack.
"""

from __future__ import annotations

import subprocess
import time
import uuid
from unittest import mock

import pytest

from src import docker_runtime
from src.heal_budget import HealBudget
from src.recovery_adapters import docker_recovery

IMAGE = "redis:7-alpine"  # already used by the test stack, so no extra pull


def _docker(*args: str) -> str:
    return subprocess.run(
        ["docker", *args], capture_output=True, text=True, timeout=60
    ).stdout.strip()


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds: float):
        self.now += seconds


@pytest.fixture
def make_container(monkeypatch):
    """Create a container, redirect the healer's "consumer" service to it, clean up after."""
    created: list[str] = []

    def factory(command: str, *, running: bool, extra: tuple[str, ...] = ()) -> str:
        name = f"it-consumer-{uuid.uuid4().hex[:6]}"
        _docker(
            "create", "--name", name, *extra, "--entrypoint", "sh", IMAGE, "-c", command
        )
        created.append(name)
        if running:
            _docker("start", name)
        monkeypatch.setattr(
            docker_runtime,
            "_name_candidates",
            lambda service, _n=name: [_n] if service == "consumer" else [service],
        )
        return name

    monkeypatch.setenv("ENABLE_DOCKER_STATUS", "true")
    monkeypatch.setenv("ENABLE_DOCKER_RECOVERY", "true")
    yield factory
    for name in created:
        _docker("rm", "-f", name)


@pytest.fixture
def agent():
    """The real agent, with its health check narrowed to the consumer.

    A full check runs seven sequential probes (~13s) and heal_component runs it
    several times per heal; narrowing keeps each scenario to seconds. The consumer
    check itself, the Docker status lookup, the plan and the actions are real.
    """
    from src.pipeline_health import PipelineHealingAgent

    a = PipelineHealingAgent()
    a.clock = FakeClock()
    a.budget = HealBudget(
        max_attempts=3,
        window_seconds=900,
        backoff_base_seconds=10,
        backoff_cap_seconds=60,
        clock=a.clock,
    )

    def consumer_only_check():
        checks = a._attach_agent_plans([a.check_consumer_state()])
        components = [c.to_dict() for c in checks]
        bad = [c for c in components if c["status"] != "healthy"]
        return {
            "overall_status": "healthy" if not bad else "unhealthy",
            "components": components,
        }

    a.full_health_check = consumer_only_check
    return a


def _state(name: str) -> str:
    return _docker("inspect", "-f", "{{.State.Status}}", name)


def _rows(h, sql, params=()):
    return h.query(sql, params)


def test_stopped_consumer_is_started_and_verified(h, agent, make_container):
    name = make_container("sleep 3600", running=True)
    _docker("stop", "-t", "1", name)
    assert _state(name) == "exited"

    result = agent.heal_component("consumer")

    assert result["status"] == "healed"
    assert _state(name) == "running"
    statuses = [
        r[0]
        for r in _rows(
            h, "SELECT status FROM pipeline_step_incidents WHERE component='consumer'"
        )
    ]
    assert "healed" in statuses


def _seed_successful_history(h, n: int = 20) -> None:
    """Make "restart the consumer" look reliable, as it would on a healthy system."""
    for _ in range(n):
        h.query(
            "INSERT INTO pipeline_step_incidents(component, problem_type, reason, recovery_action, status) "
            "VALUES ('consumer', 'consumer_container_down', 'seed', 'restart_consumer_container', 'healed') "
            "RETURNING 1"
        )


def test_crash_looping_consumer_is_given_up_on_after_the_budget(
    h, agent, make_container
):
    _seed_successful_history(
        h
    )  # restarts usually work, so the memory layer allows automatic retries
    name = make_container(
        "exit 1", running=False
    )  # dies immediately every time it starts
    with mock.patch.object(
        docker_recovery, "start_container", wraps=docker_recovery.start_container
    ) as start:
        statuses = []
        for _ in range(14):  # fourteen healer cycles, 8s apart
            statuses.append(agent.heal_component("consumer")["status"])
            agent.clock.advance(8)

    assert (
        start.call_count == 3
    ), f"expected exactly the budget of 3 starts, got {start.call_count}: {statuses}"
    assert statuses[-1] == "escalated"
    assert _state(name) != "running"
    alerts = _rows(
        h,
        "SELECT COUNT(*) FROM alert_events WHERE severity='critical' AND message LIKE '%%gave up%%'",
    )
    escalations = _rows(
        h, "SELECT COUNT(*) FROM pipeline_step_incidents WHERE status='escalated'"
    )
    assert (alerts[0][0], escalations[0][0]) == (1, 1)
    # Regression: each incident used to embed the previous ones, tripling in size every time.
    biggest = _rows(
        h,
        "SELECT MAX(pg_column_size(detected_state) + pg_column_size(verification_result)) FROM pipeline_step_incidents",
    )
    assert biggest[0][0] < 50_000, f"incident rows are growing: {biggest[0][0]} bytes"


def test_after_a_failed_restart_the_healer_asks_a_human_once(h, agent, make_container):
    """With no history, one failed restart means 0% success: stop acting, ask, and don't nag."""
    make_container("exit 1", running=False)
    with mock.patch.object(
        docker_recovery, "start_container", wraps=docker_recovery.start_container
    ) as start:
        statuses = []
        for _ in range(10):
            statuses.append(agent.heal_component("consumer")["status"])
            agent.clock.advance(8)

    assert statuses[0] == "failed" and set(statuses[1:]) == {"manual_review"}
    assert start.call_count == 1
    pending = _rows(
        h,
        "SELECT COUNT(*) FROM human_approval_requests WHERE component='consumer' AND status='pending'",
    )
    assert pending[0][0] == 1, "one open approval request, not one per healer cycle"


def test_consumer_that_recovers_gets_a_fresh_budget(h, agent, make_container):
    name = make_container("sleep 3600", running=True)
    _docker("stop", "-t", "1", name)

    assert agent.heal_component("consumer")["status"] == "healed"
    assert agent.budget.check("consumer").attempts == 0  # success wiped the history

    _docker("stop", "-t", "1", name)  # it dies again a minute later
    agent.clock.advance(60)

    assert agent.heal_component("consumer")["status"] == "healed"


def test_running_but_unhealthy_consumer_waits_for_a_human(h, agent, make_container):
    name = make_container(
        "sleep 3600",
        running=True,
        extra=(
            "--health-cmd",
            "false",
            "--health-interval",
            "1s",
            "--health-retries",
            "1",
        ),
    )
    deadline = time.time() + 30
    while (
        time.time() < deadline
        and _docker("inspect", "-f", "{{.State.Health.Status}}", name) != "unhealthy"
    ):
        time.sleep(1)
    started_at = _docker("inspect", "-f", "{{.State.StartedAt}}", name)

    with mock.patch.object(
        docker_recovery, "start_container"
    ) as start, mock.patch.object(docker_recovery, "restart_container") as restart:
        result = agent.heal_component("consumer")

    assert result["status"] == "manual_review"
    start.assert_not_called()
    restart.assert_not_called()
    assert (
        _docker("inspect", "-f", "{{.State.StartedAt}}", name) == started_at
    )  # never restarted
    pending = _rows(
        h,
        "SELECT COUNT(*) FROM human_approval_requests WHERE component='consumer' AND status='pending'",
    )
    assert pending[0][0] == 1


@pytest.mark.parametrize("action", ["start_container", "restart_container"])
def test_protected_container_is_never_touched(action, make_container, monkeypatch):
    name = make_container("sleep 3600", running=True)
    _docker("stop", "-t", "1", name)
    monkeypatch.setenv("HEALER_PROTECTED_SERVICES", f"consumer,{name}")

    result = getattr(docker_runtime, action)(name)

    assert result == {"ok": False, "service": name, "reason": "protected_service"}
    assert _state(name) == "exited"
