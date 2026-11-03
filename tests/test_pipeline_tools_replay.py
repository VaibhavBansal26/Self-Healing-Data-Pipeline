from src import pipeline_tools


class FakeProducer:
    def __init__(self, config):
        self.config = config
        self.messages = []

    def produce(self, topic, key, value):
        self.messages.append((topic, key, value))

    def flush(self):
        return None


def test_replay_dlq_event_writes_audit(monkeypatch):
    monkeypatch.setattr(pipeline_tools, "Producer", FakeProducer)
    monkeypatch.setattr(pipeline_tools, "insert_replay_audit", lambda **kwargs: 123)
    result = pipeline_tools.replay_dlq_event_tool({"event_id": "e1"}, "raw_orders", reviewer="vaibhav")
    assert result["replayed"] is True
    assert result["replay_id"] == 123
