from __future__ import annotations

import json
import time
from typing import Any, Dict
import psycopg2
import redis
from confluent_kafka import Consumer, Producer, TopicPartition
from langgraph.types import Command

from src.config import (
    KAFKA_BOOTSTRAP_SERVERS,
    RAW_TOPIC,
    DLQ_TOPIC,
    CONSUMER_GROUP,
    REDIS_HOST,
    REDIS_PORT,
    ENABLE_TERMINAL_HUMAN_APPROVAL,
    MAX_RETRY_COUNT,
)
from src.schema_registry import validate_order_event, explain_validation_error
from src.healing_graph import healing_graph
from src.db import (
    insert_order,
    insert_incident,
    IdempotencyConflictError,
    log_event_journey,
)
from src.vector_memory import store_incident_memory
from src.idempotency import payload_fingerprint
from src.metrics import (
    EVENTS_PROCESSED,
    EVENTS_VALID,
    EVENTS_FAILED,
    EVENTS_HEALED,
    EVENTS_DLQ,
    EVENTS_MANUAL_REVIEW,
    REPAIR_LATENCY,
    maybe_start_metrics_server,
    observe_latency,
)

# Short socket timeouts: a dead Redis must cost milliseconds per event, not seconds.
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True,
    socket_connect_timeout=0.5,
    socket_timeout=0.5,
)
producer = Producer({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})


class TransientInfrastructureError(Exception):
    """A dependency (database) is unavailable. The record is fine; retry it later."""


TRANSIENT_DB_ERRORS = (psycopg2.OperationalError, psycopg2.InterfaceError)


def safe_get_retry_count(retry_key: str) -> int:
    try:
        return int(redis_client.get(retry_key) or 0)
    except Exception:
        return 0


def safe_increment_retry(retry_key: str) -> None:
    try:
        redis_client.incr(retry_key)
        redis_client.expire(retry_key, 3600)
    except Exception as exc:
        print(f"Redis unavailable. Continuing without retry memory: {exc}")


def is_consumer_paused() -> bool:
    try:
        return redis_client.get("consumer:paused") == "true"
    except Exception:
        return False


def send_to_dlq(payload: Dict[str, Any], error_message: str):
    dlq_record = {"payload": payload, "error_message": error_message}
    log_event_journey(
        payload.get("event_id"),
        payload,
        "dlq",
        "kafka_dlq",
        "quarantined",
        error_message,
        "send_to_dlq",
        risk_level="high",
        metadata={"topic": DLQ_TOPIC},
    )
    producer.produce(
        DLQ_TOPIC,
        key=str(payload.get("event_id", "unknown")),
        value=json.dumps(dlq_record),
    )
    producer.flush()
    EVENTS_DLQ.inc()


def _pending_interrupt(result: Dict[str, Any], thread_id: str) -> Any:
    """Return the payload of a paused human-approval interrupt, or None.

    Newer LangGraph releases put ``__interrupt__`` in the invoke() result. The
    pinned 0.2.x does not, so also read the thread's checkpoint.
    """
    interrupts = result.get("__interrupt__")
    if interrupts:
        return interrupts[0].value if hasattr(interrupts[0], "value") else interrupts[0]
    snapshot = healing_graph.get_state({"configurable": {"thread_id": thread_id}})
    for task in snapshot.tasks:
        if task.interrupts:
            first = task.interrupts[0]
            return first.value if hasattr(first, "value") else first
    return None


def maybe_resume_after_human_interrupt(
    result: Dict[str, Any], thread_id: str
) -> Dict[str, Any]:
    interrupt_payload = _pending_interrupt(result, thread_id)
    if interrupt_payload is None:
        return result

    print("\nHuman approval required")
    print(json.dumps(interrupt_payload, indent=2, default=str))

    if not ENABLE_TERMINAL_HUMAN_APPROVAL:
        return {
            **result,
            "final_status": "manual_review",
            "human_feedback": {
                "approved": False,
                "notes": "Terminal approval disabled",
            },
        }

    user_input = input("Approve repair? Type yes or no: ").strip().lower()
    approved = user_input in {"y", "yes"}
    notes = input("Reviewer notes: ").strip()

    return healing_graph.invoke(
        Command(resume={"approved": approved, "notes": notes}),
        config={"configurable": {"thread_id": thread_id}},
    )


def record_incident_and_memory(
    payload: Dict[str, Any],
    error_type: str,
    error_message: str,
    healed_payload: Dict[str, Any] | None,
    action: str,
    risk_level: str | None,
    status: str,
    confidence: float | None = None,
    agent_trace: list[Dict[str, Any]] | None = None,
    rag_evidence: list[Dict[str, Any]] | None = None,
) -> None:
    incident_id = insert_incident(
        payload,
        error_type,
        error_message,
        healed_payload,
        action,
        risk_level,
        status,
        confidence,
        agent_trace=agent_trace,
        rag_evidence=rag_evidence,
    )
    try:
        store_incident_memory(
            incident_id, payload, error_message, action, status, healed_payload
        )
    except Exception as exc:
        print(f"Vector memory unavailable. Continuing without memory write: {exc}")


def process_payload(payload: Dict[str, Any]):
    EVENTS_PROCESSED.inc()
    log_event_journey(
        payload.get("event_id"),
        payload,
        "consumed",
        "consumer",
        "success",
        "Consumer received Kafka message",
        "consume",
    )
    fingerprint = payload_fingerprint(payload)
    retry_key = f"retry_count:{fingerprint}"
    retry_count = safe_get_retry_count(retry_key)

    if retry_count >= MAX_RETRY_COUNT:
        send_to_dlq(payload, "Max retry count exceeded")
        record_incident_and_memory(
            payload,
            "max_retry_exceeded",
            "Max retry count exceeded",
            None,
            "send_to_dlq",
            "high",
            "failed",
            1.0,
        )
        EVENTS_FAILED.inc()
        return

    try:
        order = validate_order_event(payload)
        log_event_journey(
            order.event_id,
            payload,
            "validated",
            "schema_registry",
            "success",
            "Payload passed schema validation",
            "validate",
        )
        insert_order(order)
        log_event_journey(
            order.event_id,
            order.model_dump(),
            "inserted",
            "postgres",
            "success",
            "Clean record inserted or safely skipped",
            "insert_order",
        )
        EVENTS_VALID.inc()
        print(f"Inserted or skipped valid order: {order.event_id}")
        return
    except IdempotencyConflictError as exc:
        send_to_dlq(payload, str(exc))
        log_event_journey(
            payload.get("event_id"),
            payload,
            "idempotency_conflict",
            "postgres",
            "failed",
            str(exc),
            "send_to_dlq",
            risk_level="high",
        )
        record_incident_and_memory(
            payload,
            "idempotency_conflict",
            str(exc),
            None,
            "send_to_dlq",
            "high",
            "failed",
            1.0,
        )
        EVENTS_FAILED.inc()
        return
    except Exception as exc:
        if isinstance(exc, TRANSIENT_DB_ERRORS):
            # Not a data problem: never route to the repair agent, the DLQ, or burn
            # the record's retry budget because the database is down.
            raise TransientInfrastructureError(str(exc)) from exc
        error_message = explain_validation_error(payload, exc)
        safe_increment_retry(retry_key)
        log_event_journey(
            payload.get("event_id"),
            payload,
            "validation_failed",
            "schema_registry",
            "failed",
            error_message,
            "start_agent",
        )
        print(f"Validation failed. Starting self healing graph. Error: {error_message}")

        thread_id = fingerprint
        initial_state = {
            "original_payload": payload,
            "healed_payload": None,
            "error_type": "validation_error",
            "error_message": error_message,
            "similar_incidents": [],
            "decision": None,
            "human_feedback": None,
            "verified": False,
            "final_status": "pending",
        }

        with observe_latency(REPAIR_LATENCY):
            result = healing_graph.invoke(
                initial_state, config={"configurable": {"thread_id": thread_id}}
            )
            result = maybe_resume_after_human_interrupt(result, thread_id)

        decision = result.get("decision") or {}
        agent_trace = result.get("agent_trace") or []
        rag_evidence = result.get("similar_incidents") or []
        final_status = result.get("final_status", "failed")
        log_event_journey(
            payload.get("event_id"),
            payload,
            "agent_decision",
            "langgraph_agent",
            final_status,
            decision.get("reason"),
            action=decision.get("action"),
            risk_level=decision.get("risk_level"),
            metadata={"agent_trace": agent_trace, "rag_evidence": rag_evidence},
        )
        healed_payload = result.get("healed_payload")
        action = decision.get("action", "send_to_dlq")
        risk_level = decision.get("risk_level")
        confidence = decision.get("confidence")

        if final_status == "healed" and healed_payload:
            try:
                healed_order = validate_order_event(healed_payload)
                insert_order(healed_order)
                try:
                    redis_client.set(
                        f"healed:{fingerprint}",
                        json.dumps(
                            {
                                "original": payload,
                                "healed": healed_payload,
                                "action": action,
                            }
                        ),
                        ex=86400,
                    )
                except Exception:
                    pass
                log_event_journey(
                    healed_order.event_id,
                    healed_payload,
                    "agent_healed",
                    "langgraph_agent",
                    "success",
                    "Reason Act Verify passed and healed record was inserted",
                    action,
                    risk_level,
                    metadata={"agent_trace": agent_trace},
                )
                record_incident_and_memory(
                    payload,
                    "validation_error",
                    error_message,
                    healed_payload,
                    action,
                    risk_level,
                    "healed",
                    confidence,
                    agent_trace,
                    rag_evidence,
                )
                EVENTS_HEALED.inc()
                print(f"Healed and inserted order: {healed_order.event_id}")
            except Exception as insert_exc:
                if isinstance(insert_exc, TRANSIENT_DB_ERRORS):
                    raise TransientInfrastructureError(str(insert_exc)) from insert_exc
                send_to_dlq(payload, str(insert_exc))
                record_incident_and_memory(
                    payload,
                    "post_healing_insert_failure",
                    str(insert_exc),
                    healed_payload,
                    action,
                    "high",
                    "failed",
                    confidence,
                    agent_trace,
                    rag_evidence,
                )
                EVENTS_FAILED.inc()

        elif final_status == "manual_review":
            log_event_journey(
                payload.get("event_id"),
                payload,
                "human_review",
                "approval_queue",
                "pending",
                "Risk gate requires human approval",
                action,
                risk_level,
                metadata={"agent_trace": agent_trace},
            )
            record_incident_and_memory(
                payload,
                "validation_error",
                error_message,
                healed_payload,
                action,
                risk_level,
                "manual_review",
                confidence,
                agent_trace,
                rag_evidence,
            )
            EVENTS_MANUAL_REVIEW.inc()
            print("Routed to manual review")

        else:
            send_to_dlq(payload, error_message)
            record_incident_and_memory(
                payload,
                "validation_error",
                error_message,
                healed_payload,
                action,
                risk_level,
                "failed",
                confidence,
                agent_trace,
                rag_evidence,
            )
            EVENTS_FAILED.inc()
            print("Sent to DLQ")


class FailureTracker:
    """Consecutive failures on one offset, with capped exponential backoff."""

    def __init__(self, base: float = 1.0, cap: float = 15.0):
        self.base, self.cap = base, cap
        self.key: tuple[int, int] | None = None
        self.attempts = 0

    def record(self, partition: int, offset: int) -> float:
        key = (partition, offset)
        self.attempts = self.attempts + 1 if key == self.key else 1
        self.key = key
        return min(self.cap, self.base * 2 ** (self.attempts - 1))

    def reset(self) -> None:
        self.key, self.attempts = None, 0


def _safe_payload(msg) -> Dict[str, Any]:
    try:
        value = json.loads(msg.value().decode("utf-8"))
        return value if isinstance(value, dict) else {"raw": value}
    except Exception:
        return {"raw": msg.value().decode("utf-8", errors="replace")}


def start_consumer():
    maybe_start_metrics_server()
    consumer = Consumer(
        {
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
            "group.id": CONSUMER_GROUP,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )
    consumer.subscribe([RAW_TOPIC])
    failures = FailureTracker()
    print("Consumer started")

    try:
        while True:
            if is_consumer_paused():
                print("Consumer paused from dashboard/API control")
                time.sleep(2)
                continue

            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                print(f"Kafka error: {msg.error()}")
                continue

            try:
                payload = json.loads(msg.value().decode("utf-8"))
                process_payload(payload)
                consumer.commit(msg)
                failures.reset()
            except Exception as exc:
                EVENTS_FAILED.inc()
                transient = isinstance(
                    exc, (TransientInfrastructureError, *TRANSIENT_DB_ERRORS)
                )
                delay = failures.record(msg.partition(), msg.offset())
                print(
                    f"Processing failed ({'transient' if transient else 'unexpected'}): {exc}"
                )
                if not transient and failures.attempts > MAX_RETRY_COUNT:
                    # Poison message: park it instead of blocking the partition forever.
                    send_to_dlq(
                        _safe_payload(msg),
                        f"Unprocessable after {MAX_RETRY_COUNT} attempts: {exc}",
                    )
                    consumer.commit(msg)
                    failures.reset()
                    continue
                # Rewind to the failed offset so it is retried, never skipped.
                consumer.seek(
                    TopicPartition(msg.topic(), msg.partition(), msg.offset())
                )
                time.sleep(delay)
    finally:
        consumer.close()


if __name__ == "__main__":
    start_consumer()
