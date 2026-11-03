from unittest.mock import MagicMock

import pytest

from src import dashboard_service


class FakeCursor:
    def __init__(self, row=None, rows=None):
        self.row = row
        self.rows = rows or []
        self.executed = []

    def execute(self, query, params=None):
        self.executed.append((query, params))

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_get_pipeline_summary_includes_dlq_count(monkeypatch):
    cursor = FakeCursor(row=(10, 4, 2, 1, 1, 2))
    monkeypatch.setattr(
        dashboard_service, "get_db_connection", lambda: FakeConnection(cursor)
    )
    monkeypatch.setattr(
        dashboard_service,
        "call_pipeline_tool",
        lambda name, **kwargs: {"message_count": 3},
    )

    summary = dashboard_service.get_pipeline_summary()

    assert summary["orders_count"] == 10
    assert summary["healed_count"] == 2
    assert summary["unresolved_count"] == 2
    assert summary["dlq_count"] == 3


def test_update_incident_status_rejects_unknown_status():
    with pytest.raises(ValueError):
        dashboard_service.update_incident_status(1, "unknown")


def test_update_incident_status_returns_updated(monkeypatch):
    cursor = FakeCursor(row=(7, "evt_7", "approved_for_replay"))
    monkeypatch.setattr(
        dashboard_service, "get_db_connection", lambda: FakeConnection(cursor)
    )

    result = dashboard_service.update_incident_status(
        7, "approved_for_replay", "looks safe"
    )

    assert result == {
        "updated": True,
        "incident_id": 7,
        "event_id": "evt_7",
        "status": "approved_for_replay",
    }


def test_run_reconciliation_now_uses_tool_layer(monkeypatch):
    tool = MagicMock(return_value={"status": "completed"})
    monkeypatch.setattr(dashboard_service, "call_pipeline_tool", tool)

    result = dashboard_service.run_reconciliation_now()

    assert result == {"status": "completed"}
    tool.assert_called_once_with("run_reconciliation")
