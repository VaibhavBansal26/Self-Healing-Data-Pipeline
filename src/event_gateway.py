"""Kafka event gateway used by producer, API, and dashboard."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from confluent_kafka import Producer

from src.config import KAFKA_BOOTSTRAP_SERVERS, RAW_TOPIC
from src.data_catalog import demo_order_events
from src.transformations import transform_order_payload
from src.db import log_event_journey


def _producer() -> Producer:
    return Producer({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})


def publish_event(payload: Dict[str, Any], topic: str = RAW_TOPIC, transform: bool = False) -> Dict[str, Any]:
    event_payload = payload
    steps: List[str] = []
    if transform:
        event_payload, steps = transform_order_payload(payload)

    producer = _producer()
    producer.produce(topic, key=str(event_payload.get("event_id", "unknown")), value=json.dumps(event_payload))
    producer.flush()
    log_event_journey(event_payload.get("event_id"), event_payload, "published", "producer_api", "success", "Event published to Kafka", "produce", metadata={"topic": topic, "transformation_steps": steps})
    return {"published": True, "topic": topic, "event_id": event_payload.get("event_id"), "payload": event_payload, "transformation_steps": steps}


def publish_events(payloads: List[Dict[str, Any]], topic: str = RAW_TOPIC, transform: bool = False) -> Dict[str, Any]:
    results = [publish_event(payload, topic=topic, transform=transform) for payload in payloads]
    return {"published_count": len(results), "topic": topic, "events": results}


def publish_demo_events(topic: str = RAW_TOPIC, transform: bool = False) -> Dict[str, Any]:
    return publish_events(demo_order_events(), topic=topic, transform=transform)
