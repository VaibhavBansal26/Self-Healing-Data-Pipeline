"""Fixtures for end-to-end tests against real Kafka, Postgres and Redis.

Run with:  make test-integration   (or see tests/integration/README.md)

The env vars below must be set before any ``src.*`` module is imported, because
``src.config`` reads them at import time. That is why these tests run in their
own pytest invocation and are ignored by the default ``pytest tests`` run.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid

import pytest

if os.getenv("RUN_INTEGRATION") == "1":
    os.environ.update(
        {
            "KAFKA_BOOTSTRAP_SERVERS": "localhost:19092",
            "POSTGRES_HOST": "localhost",
            "POSTGRES_PORT": "55442",
            "POSTGRES_DB": "pipeline_db",
            "POSTGRES_USER": "postgres",
            "POSTGRES_PASSWORD": "postgres",
            "REDIS_HOST": "localhost",
            "REDIS_PORT": "56379",
            "RAW_TOPIC": "it_raw_orders",
            "DLQ_TOPIC": "it_dead_letter_events",
            "CONSUMER_GROUP": f"it-group-{uuid.uuid4().hex[:8]}",
            "ENABLE_TERMINAL_HUMAN_APPROVAL": "false",
            "ENABLE_PROMETHEUS_SERVER": "false",
            "MAX_RETRY_COUNT": "3",
        }
    )
    # Keep the LLM and vector memory out of the loop: these tests cover the
    # deterministic path and must not depend on, or spend, an API key.
    os.environ.pop("OPENAI_API_KEY", None)


def pytest_ignore_collect(collection_path, config):
    return os.getenv("RUN_INTEGRATION") != "1" and collection_path.name != "conftest.py"


@pytest.fixture(scope="session")
def infra():
    from confluent_kafka.admin import AdminClient, NewTopic

    from src.config import DLQ_TOPIC, KAFKA_BOOTSTRAP_SERVERS, RAW_TOPIC

    admin = AdminClient({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})
    deadline = time.time() + 60
    while True:
        try:
            admin.list_topics(timeout=3)
            break
        except Exception:
            if time.time() > deadline:
                pytest.fail(
                    "Kafka not reachable on localhost:19092; start the test stack first"
                )
            time.sleep(1)
    futures = admin.create_topics([NewTopic(t, 1, 1) for t in (RAW_TOPIC, DLQ_TOPIC)])
    for fut in futures.values():
        try:
            fut.result(timeout=15)
        except Exception as exc:  # topic may already exist from a previous run
            if "TOPIC_ALREADY_EXISTS" not in str(exc):
                raise
    return admin


@pytest.fixture(autouse=True)
def clean_state(infra):
    from src.consumer import redis_client
    from src.db import get_db_connection

    redis_client.flushdb()
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "TRUNCATE orders, pipeline_incidents, event_journey RESTART IDENTITY CASCADE;"
            )
    yield


@pytest.fixture(scope="session")
def running_consumer(infra):
    """Run the real consumer loop in a background thread for the whole session."""
    from src.consumer import start_consumer

    thread = threading.Thread(target=start_consumer, daemon=True, name="it-consumer")
    thread.start()
    time.sleep(3)  # let the group join and get its partition assignment
    return thread


class Helpers:
    @staticmethod
    def publish(payload: dict) -> None:
        from confluent_kafka import Producer

        from src.config import KAFKA_BOOTSTRAP_SERVERS, RAW_TOPIC

        producer = Producer({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})
        producer.produce(
            RAW_TOPIC, key=str(payload.get("event_id")), value=json.dumps(payload)
        )
        producer.flush(10)

    @staticmethod
    def query(sql: str, params=()):
        from src.db import get_db_connection

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchall()

    @staticmethod
    def wait_for(predicate, timeout: float = 45.0, interval: float = 0.5):
        deadline = time.time() + timeout
        last = None
        while time.time() < deadline:
            last = predicate()
            if last:
                return last
            time.sleep(interval)
        return last

    @staticmethod
    def dlq_messages(match, timeout: float = 30.0) -> list[dict]:
        """Read the DLQ from the start until a message satisfying ``match`` appears."""
        from confluent_kafka import Consumer

        from src.config import DLQ_TOPIC, KAFKA_BOOTSTRAP_SERVERS

        consumer = Consumer(
            {
                "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
                "group.id": f"it-dlq-reader-{uuid.uuid4().hex[:6]}",
                "auto.offset.reset": "earliest",
            }
        )
        consumer.subscribe([DLQ_TOPIC])
        out: list[dict] = []
        deadline = time.time() + timeout
        try:
            while time.time() < deadline and not any(match(m) for m in out):
                msg = consumer.poll(1.0)
                if msg is not None and not msg.error():
                    out.append(json.loads(msg.value().decode("utf-8")))
        finally:
            consumer.close()
        return out


@pytest.fixture
def h():
    return Helpers
