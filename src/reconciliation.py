from __future__ import annotations

from datetime import datetime
from src.config import KAFKA_BOOTSTRAP_SERVERS, DLQ_TOPIC
from src.db import count_orders_and_incidents, insert_reconciliation_run


def get_topic_message_count(topic: str) -> int:
    from confluent_kafka import Consumer, TopicPartition

    consumer = Consumer(
        {
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
            "group.id": f"reconciliation_counter_{datetime.utcnow().timestamp()}",
            "enable.auto.commit": False,
        }
    )
    try:
        metadata = consumer.list_topics(topic=topic, timeout=10)
        if topic not in metadata.topics:
            return 0
        partitions = metadata.topics[topic].partitions.keys()
        total = 0
        for partition in partitions:
            tp = TopicPartition(topic, partition)
            low, high = consumer.get_watermark_offsets(tp, timeout=10)
            total += high - low
        return total
    except Exception as exc:
        print(f"Could not count topic {topic}: {exc}")
        return 0
    finally:
        consumer.close()


def run_daily_reconciliation() -> str:
    orders_count, incident_count, unresolved = count_orders_and_incidents()
    dlq_count = get_topic_message_count(DLQ_TOPIC)
    notes = (
        f"Reconciliation completed. orders={orders_count}, "
        f"incidents={incident_count}, dlq={dlq_count}, unresolved={unresolved}"
    )
    insert_reconciliation_run(
        orders_count, incident_count, dlq_count, unresolved, notes
    )
    print(notes)
    return notes


if __name__ == "__main__":
    run_daily_reconciliation()
