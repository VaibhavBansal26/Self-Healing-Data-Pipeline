from __future__ import annotations

from typing import Any, Dict
from confluent_kafka.admin import AdminClient, NewTopic
from src.config import KAFKA_BOOTSTRAP_SERVERS


def ensure_topic(topic: str, partitions: int = 1, replication_factor: int = 1) -> Dict[str, Any]:
    admin = AdminClient({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})
    topics = set(admin.list_topics(timeout=5).topics.keys())
    if topic in topics:
        return {"ok": True, "action": "already_exists", "topic": topic}
    futures = admin.create_topics([NewTopic(topic, partitions, replication_factor)])
    out: Dict[str, Any] = {}
    for name, fut in futures.items():
        try:
            fut.result(timeout=10)
            out[name] = "created"
        except Exception as exc:
            out[name] = str(exc)
    return {"ok": topic in out and "created" in out[topic], "action": "create_topic", "topic": topic, "result": out}


def topic_inventory() -> Dict[str, Any]:
    admin = AdminClient({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})
    meta = admin.list_topics(timeout=5)
    return {"topics": sorted(meta.topics.keys()), "broker_count": len(meta.brokers)}
