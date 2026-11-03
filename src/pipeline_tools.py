"""Shared business tools used by both LangGraph and the MCP server.

The MCP server imports these functions and exposes them as MCP tools.
The LangGraph app can also call them through src.mcp_layer.tool_client so local
runs do not require keeping a separate MCP process alive.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from src.metrics import DLQ_REPLAY_SUCCESS, DLQ_REPLAY_FAILURE

from src.config import KAFKA_BOOTSTRAP_SERVERS, DLQ_TOPIC, REDIS_HOST, REDIS_PORT
from src.db import get_db_connection, insert_replay_audit
from src.reconciliation import get_topic_message_count, run_daily_reconciliation
from src.vector_memory import search_similar_incidents

Producer = None
Consumer = None
TopicPartition = None


def _redis_client():
    import redis

    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


def search_similar_incidents_tool(
    payload: Dict[str, Any],
    error_message: str,
    k: int = 3,
) -> List[Dict[str, Any]]:
    """Search Chroma vector memory for incidents similar to the current failure."""
    return search_similar_incidents(payload, error_message, k=k)


def get_redis_retry_count_tool(fingerprint: str) -> Dict[str, Any]:
    """Return the retry count stored in Redis for a failed payload fingerprint."""
    value = _redis_client().get(f"retry_count:{fingerprint}")
    return {"fingerprint": fingerprint, "retry_count": int(value or 0)}


def query_recent_incidents_tool(
    limit: int = 10, status: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Read recent incidents from PostgreSQL for debugging and agent context."""
    limit = max(1, min(limit, 50))
    params: list[Any] = []
    where = ""
    if status:
        where = "WHERE status = %s"
        params.append(status)

    query = f"""
    SELECT incident_id, event_id, error_type, error_message, original_payload,
           healed_payload, healing_action, risk_level, status, created_at
    FROM pipeline_incidents
    {where}
    ORDER BY created_at DESC
    LIMIT %s;
    """
    params.append(limit)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

    incidents = []
    for row in rows:
        incidents.append(
            {
                "incident_id": row[0],
                "event_id": row[1],
                "error_type": row[2],
                "error_message": row[3],
                "original_payload": row[4],
                "healed_payload": row[5],
                "healing_action": row[6],
                "risk_level": row[7],
                "status": row[8],
                "created_at": row[9].isoformat() if row[9] else None,
            }
        )
    return incidents


def get_order_tool(event_id: str) -> Dict[str, Any]:
    """Look up one ingested order by event_id."""
    query = """
    SELECT event_id, customer_id, amount, currency, status, created_at
    FROM orders
    WHERE event_id = %s;
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (event_id,))
            row = cur.fetchone()

    if not row:
        return {"found": False, "event_id": event_id}

    return {
        "found": True,
        "event_id": row[0],
        "customer_id": row[1],
        "amount": float(row[2]),
        "currency": row[3],
        "status": row[4],
        "created_at": row[5].isoformat() if row[5] else None,
    }


def get_dlq_count_tool() -> Dict[str, Any]:
    """Return approximate number of messages currently retained in the DLQ topic."""
    return {"topic": DLQ_TOPIC, "message_count": get_topic_message_count(DLQ_TOPIC)}


def peek_dlq_tool(max_messages: int = 5) -> List[Dict[str, Any]]:
    """Read a small DLQ sample without committing offsets for debugging."""
    max_messages = max(1, min(max_messages, 20))
    global Consumer, TopicPartition
    if Consumer is None or TopicPartition is None:
        from confluent_kafka import (
            Consumer as _Consumer,
            TopicPartition as _TopicPartition,
        )

        Consumer = _Consumer
        TopicPartition = _TopicPartition
    consumer = Consumer(
        {
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
            "group.id": "mcp_dlq_peek_debugger",
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
        }
    )
    messages: List[Dict[str, Any]] = []
    try:
        metadata = consumer.list_topics(topic=DLQ_TOPIC, timeout=10)
        if DLQ_TOPIC not in metadata.topics:
            return []
        partitions = list(metadata.topics[DLQ_TOPIC].partitions.keys())
        topic_partitions = [TopicPartition(DLQ_TOPIC, p, 0) for p in partitions]
        consumer.assign(topic_partitions)

        while len(messages) < max_messages:
            msg = consumer.poll(1.0)
            if msg is None:
                break
            if msg.error():
                continue
            try:
                value = json.loads(msg.value().decode("utf-8"))
            except Exception:
                value = msg.value().decode("utf-8", errors="replace")
            messages.append(
                {
                    "topic": msg.topic(),
                    "partition": msg.partition(),
                    "offset": msg.offset(),
                    "key": msg.key().decode("utf-8") if msg.key() else None,
                    "value": value,
                }
            )
    finally:
        consumer.close()
    return messages


def replay_dlq_event_tool(
    payload: Dict[str, Any],
    target_topic: str,
    reviewer: Optional[str] = None,
    reviewer_notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Replay a reviewed payload to a target Kafka topic and write an audit trail."""
    global Producer
    if Producer is None:
        from confluent_kafka import Producer as _Producer

        Producer = _Producer
    producer = Producer({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})
    key = str(payload.get("event_id", "replayed"))
    try:
        producer.produce(target_topic, key=key, value=json.dumps(payload))
        producer.flush()
        replay_id = insert_replay_audit(
            original_payload=payload,
            replayed_payload=payload,
            replay_status="success",
            reviewer=reviewer,
            reviewer_notes=reviewer_notes,
        )
        DLQ_REPLAY_SUCCESS.inc()
        return {
            "replayed": True,
            "target_topic": target_topic,
            "event_id": payload.get("event_id"),
            "replay_id": replay_id,
        }
    except Exception as exc:
        replay_id = insert_replay_audit(
            original_payload=payload,
            replayed_payload=None,
            replay_status="failed",
            reviewer=reviewer,
            reviewer_notes=reviewer_notes,
            failure_reason=str(exc),
        )
        DLQ_REPLAY_FAILURE.inc()
        return {
            "replayed": False,
            "target_topic": target_topic,
            "event_id": payload.get("event_id"),
            "replay_id": replay_id,
            "error": str(exc),
        }


def run_reconciliation_tool() -> Dict[str, Any]:
    """Run the same reconciliation logic used by the Airflow DAG."""
    notes = run_daily_reconciliation()
    return {"status": "completed", "notes": notes}
