from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator
from src.config import ENABLE_PROMETHEUS_SERVER, METRICS_PORT

try:
    from prometheus_client import Counter, Histogram, Gauge, start_http_server
except Exception:  # keeps unit tests importable before requirements are installed

    class _Metric:
        def __init__(self, *args, **kwargs):
            pass

        def inc(self, *args, **kwargs):
            pass

        def observe(self, *args, **kwargs):
            pass

        def set(self, *args, **kwargs):
            pass

        def labels(self, *args, **kwargs):
            return self

    Counter = Histogram = Gauge = _Metric  # type: ignore

    def start_http_server(*args, **kwargs):  # type: ignore
        return None


EVENTS_PROCESSED = Counter("events_processed_total", "Total Kafka events processed")
EVENTS_VALID = Counter("events_valid_total", "Events accepted without repair")
EVENTS_FAILED = Counter("events_failed_total", "Events that failed processing")
EVENTS_HEALED = Counter("events_healed_total", "Events successfully healed")
EVENTS_DLQ = Counter("events_sent_to_dlq_total", "Events sent to dead letter queue")
EVENTS_MANUAL_REVIEW = Counter("manual_review_total", "Events routed for human review")
DLQ_REPLAY_SUCCESS = Counter(
    "dlq_replay_success_total", "DLQ replay attempts that succeeded"
)
DLQ_REPLAY_FAILURE = Counter(
    "dlq_replay_failure_total", "DLQ replay attempts that failed"
)
REPAIR_LATENCY = Histogram("repair_latency_seconds", "Time spent in healing workflow")
DB_INSERT_LATENCY = Histogram(
    "database_insert_latency_seconds", "PostgreSQL insert latency"
)
CONSUMER_LAG = Gauge(
    "consumer_lag", "Kafka consumer lag by partition", ["topic", "partition"]
)

_started = False


def maybe_start_metrics_server() -> None:
    global _started
    if ENABLE_PROMETHEUS_SERVER and not _started:
        start_http_server(METRICS_PORT)
        _started = True


@contextmanager
def observe_latency(histogram: Histogram) -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        histogram.observe(time.perf_counter() - start)
