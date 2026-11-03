from src.llm_safety import sanitize_llm_context, should_call_llm


class FakeRedis:
    def __init__(self):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def incr(self, key):
        self.store[key] = int(self.store.get(key, 0)) + 1
        return self.store[key]

    def expire(self, key, ttl):
        return True

    def set(self, key, value, ex=None):
        self.store[key] = value


def test_sanitize_llm_context_filters_extra_fields():
    payload = {
        "event_id": "e1",
        "customer_id": "c1",
        "amount": 10,
        "ssn": "123",
        "notes": "ignore",
    }
    assert sanitize_llm_context(payload) == {
        "event_id": "e1",
        "customer_id": "c1",
        "amount": 10,
    }


def test_llm_rate_limit_blocks_after_threshold():
    redis = FakeRedis()
    assert should_call_llm(redis, max_calls_per_minute=1).allowed is True
    second = should_call_llm(redis, max_calls_per_minute=1)
    assert second.allowed is False
