from __future__ import annotations

from typing import Any, Dict, List

from src.config import KAFKA_BOOTSTRAP_SERVERS, RAW_TOPIC, CONSUMER_GROUP


def get_consumer_lag(topic: str = RAW_TOPIC, group_id: str = CONSUMER_GROUP) -> Dict[str, Any]:
    """Return Kafka lag for a consumer group.

    Works when Kafka is running. In local docs/tests without Kafka, it returns a
    structured unavailable response instead of raising.
    """
    consumer = None
    try:
        from confluent_kafka import Consumer, TopicPartition
        consumer = Consumer({
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
            "group.id": f"lag-check-{group_id}",
            "enable.auto.commit": False,
            "socket.timeout.ms": 3000,
        })
        metadata = consumer.list_topics(topic=topic, timeout=3)
        if topic not in metadata.topics:
            return {"status": "topic_missing", "topic": topic, "partitions": [], "total_lag": 0}
        partitions = sorted(metadata.topics[topic].partitions.keys())
        rows: List[Dict[str, Any]] = []
        total_lag = 0
        for partition in partitions:
            tp = TopicPartition(topic, partition)
            low, high = consumer.get_watermark_offsets(tp, timeout=3)
            committed = consumer.committed([tp], timeout=3)[0].offset
            if committed < 0:
                committed = low
            lag = max(0, high - committed)
            total_lag += lag
            rows.append({
                "topic": topic,
                "partition": partition,
                "low_offset": low,
                "latest_offset": high,
                "committed_offset": committed,
                "lag": lag,
                "consumer_group": group_id,
            })
        return {"status": "ok", "topic": topic, "consumer_group": group_id, "total_lag": total_lag, "partitions": rows}
    except Exception as exc:
        return {"status": "unavailable", "topic": topic, "consumer_group": group_id, "error": str(exc), "total_lag": None, "partitions": []}
    finally:
        if consumer is not None:
            consumer.close()
