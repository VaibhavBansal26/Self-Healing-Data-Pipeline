"""Fault injection: kill the consumer and take infrastructure down while events flow.

Pass criteria for every scenario:
  * no loss        - every published event ends up in ``orders``
  * no duplication - ``orders`` has exactly one row per event
  * no misrouting  - valid events never land in the DLQ because of an outage
"""

from __future__ import annotations

import time
import uuid

import pytest
from chaos import ConsumerProcess, compose, record, wait_service_healthy


@pytest.fixture
def consumer(chaos_topic):
    proc = ConsumerProcess(chaos_topic)
    yield proc
    proc.stop()


def _events(n: int, tag: str) -> list[dict]:
    return [
        {
            "event_id": f"{tag}-{i:04d}",
            "customer_id": f"cust-{tag}",
            "amount": 10.0 + i,
            "currency": "USD",
            "status": "paid",
        }
        for i in range(n)
    ]


def _publish(topic: str, events: list[dict]) -> None:
    import json

    from confluent_kafka import Producer

    from src.config import KAFKA_BOOTSTRAP_SERVERS

    producer = Producer({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})
    for e in events:
        producer.produce(topic, key=e["event_id"], value=json.dumps(e))
    producer.flush(30)


def _stored(h, tag: str) -> tuple[int, int]:
    """(rows, distinct event ids) for a test's events."""
    rows = h.query(
        "SELECT COUNT(*), COUNT(DISTINCT event_id) FROM orders WHERE customer_id=%s",
        (f"cust-{tag}",),
    )
    return int(rows[0][0]), int(rows[0][1])


def _dlq_has_tag(tag: str) -> bool:
    import json

    from confluent_kafka import Consumer

    from src.config import DLQ_TOPIC, KAFKA_BOOTSTRAP_SERVERS

    c = Consumer(
        {
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
            "group.id": f"chaos-dlq-{uuid.uuid4().hex[:6]}",
            "auto.offset.reset": "earliest",
        }
    )
    c.subscribe([DLQ_TOPIC])
    end = time.time() + 6
    try:
        while time.time() < end:
            msg = c.poll(1.0)
            if msg is not None and not msg.error():
                if tag in json.dumps(json.loads(msg.value())):
                    return True
    finally:
        c.close()
    return False


def _wait_all(h, tag: str, expected: int, timeout: float) -> float | None:
    """Seconds until all events are stored, or None on timeout."""
    start = time.time()
    while time.time() - start < timeout:
        if _stored(h, tag)[0] >= expected:
            return time.time() - start
        time.sleep(0.5)
    return None


def test_consumer_sigkill_midstream_loses_nothing(h, consumer, chaos_topic):
    tag = f"kill{uuid.uuid4().hex[:4]}"
    events = _events(300, tag)
    _publish(chaos_topic, events)

    consumer.start()
    assert h.wait_for(lambda: _stored(h, tag)[0] >= 20, timeout=60), consumer.log_tail()
    consumer.kill()
    stored_at_kill = _stored(h, tag)[0]
    assert stored_at_kill < len(
        events
    ), "consumer finished before the kill; increase the batch"

    consumer.start()
    recovery = _wait_all(h, tag, len(events), timeout=90)

    rows, distinct = _stored(h, tag)
    record(
        "consumer_sigkill",
        events=len(events),
        stored_at_kill=stored_at_kill,
        rows=rows,
        distinct=distinct,
        seconds_to_full_recovery=None if recovery is None else round(recovery, 1),
    )
    assert (rows, distinct) == (len(events), len(events)), consumer.log_tail()


def test_postgres_outage_loses_nothing_and_misroutes_nothing(h, consumer, chaos_topic):
    tag = f"pg{uuid.uuid4().hex[:4]}"
    first, second = _events(40, tag + "a"), _events(40, tag + "b")
    consumer.start()
    time.sleep(4)
    _publish(chaos_topic, first)
    assert (
        _wait_all(h, tag + "a", len(first), timeout=60) is not None
    ), consumer.log_tail()

    compose("stop", "postgres")
    try:
        _publish(chaos_topic, second)
        time.sleep(8)  # the consumer sees failures while the DB is down
    finally:
        compose("start", "postgres")
        wait_service_healthy("postgres")

    recovery = _wait_all(h, tag + "b", len(second), timeout=90)
    rows_b, distinct_b = _stored(h, tag + "b")
    misrouted = _dlq_has_tag(tag + "b")
    record(
        "postgres_outage",
        published_during_outage=len(second),
        stored_after=rows_b,
        distinct=distinct_b,
        valid_events_sent_to_dlq=misrouted,
        seconds_to_full_recovery=None if recovery is None else round(recovery, 1),
    )

    assert (
        not misrouted
    ), "valid events were dead-lettered because the database was down"
    assert (rows_b, distinct_b) == (len(second), len(second)), consumer.log_tail()


def test_redis_outage_does_not_stop_processing(h, consumer, chaos_topic):
    tag = f"rd{uuid.uuid4().hex[:4]}"
    events = _events(40, tag)
    consumer.start()
    time.sleep(4)

    compose("stop", "redis")
    try:
        _publish(chaos_topic, events)
        recovery = _wait_all(h, tag, len(events), timeout=60)
    finally:
        compose("start", "redis")
        wait_service_healthy("redis")

    rows, distinct = _stored(h, tag)
    record(
        "redis_outage",
        events=len(events),
        stored=rows,
        distinct=distinct,
        seconds_to_full_processing=None if recovery is None else round(recovery, 1),
    )
    assert (rows, distinct) == (len(events), len(events)), consumer.log_tail()


def test_kafka_broker_restart_consumer_resumes(h, consumer, chaos_topic):
    tag = f"kf{uuid.uuid4().hex[:4]}"
    consumer.start()
    time.sleep(4)

    compose("restart", "kafka")
    wait_service_healthy("kafka")
    events = _events(40, tag)
    _publish(chaos_topic, events)
    recovery = _wait_all(h, tag, len(events), timeout=120)

    rows, distinct = _stored(h, tag)
    record(
        "kafka_restart",
        events=len(events),
        stored=rows,
        distinct=distinct,
        consumer_alive=consumer.alive(),
        seconds_to_full_processing=None if recovery is None else round(recovery, 1),
    )
    assert (rows, distinct) == (len(events), len(events)), consumer.log_tail()
