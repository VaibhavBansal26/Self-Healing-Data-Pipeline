from __future__ import annotations

import argparse
import json
import random
import time
from confluent_kafka import Producer
from src.config import KAFKA_BOOTSTRAP_SERVERS, RAW_TOPIC

STATUSES = ["created", "paid", "cancelled", "refunded", "PAY", "create", "bad_status"]


def make_event(i: int, bad_rate: float) -> dict:
    event = {
        "event_id": f"load_evt_{i}",
        "customer_id": f"cust_{random.randint(1, 5000)}",
        "amount": round(random.uniform(1, 500), 2),
        "currency": "USD",
        "status": random.choice(STATUSES[:4]),
        "schema_version": 1,
    }
    if random.random() < bad_rate:
        failure_type = random.choice(
            [
                "amount_as_string",
                "missing_currency",
                "bad_status",
                "negative_amount",
                "missing_customer",
            ]
        )
        if failure_type == "amount_as_string":
            event["amount"] = str(event["amount"])
        elif failure_type == "missing_currency":
            event.pop("currency", None)
        elif failure_type == "bad_status":
            event["status"] = random.choice(["PAY", "create", "unknown"])
        elif failure_type == "negative_amount":
            event["amount"] = -1 * float(event["amount"])
        elif failure_type == "missing_customer":
            event.pop("customer_id", None)
    return event


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=int, default=10000)
    parser.add_argument("--bad-rate", type=float, default=0.10)
    parser.add_argument("--topic", default=RAW_TOPIC)
    args = parser.parse_args()

    producer = Producer({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})
    start = time.perf_counter()
    for i in range(args.events):
        event = make_event(i, args.bad_rate)
        producer.produce(
            args.topic, key=event.get("event_id", str(i)), value=json.dumps(event)
        )
        producer.poll(0)
    producer.flush()
    elapsed = time.perf_counter() - start
    print(
        f"Produced {args.events} events in {elapsed:.2f}s = {args.events / max(elapsed, 0.001):.2f} events/sec"
    )


if __name__ == "__main__":
    main()
