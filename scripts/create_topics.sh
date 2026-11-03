#!/usr/bin/env bash
set -euo pipefail

# Docker Compose service-name based topic creation. This works even when the
# concrete container name changes between project folders.
if docker compose ps kafka >/dev/null 2>&1; then
  docker compose up -d zookeeper kafka >/dev/null
  KAFKA_CMD=(docker compose exec -T kafka kafka-topics --bootstrap-server kafka:9092)
else
  KAFKA_CONTAINER="${KAFKA_CONTAINER:-healing_kafka}"
  KAFKA_CMD=(docker exec -i "$KAFKA_CONTAINER" kafka-topics --bootstrap-server kafka:9092)
fi

"${KAFKA_CMD[@]}" --create --if-not-exists --topic raw_orders --partitions 1 --replication-factor 1
"${KAFKA_CMD[@]}" --create --if-not-exists --topic dead_letter_events --partitions 1 --replication-factor 1

echo "Kafka topics available:"
"${KAFKA_CMD[@]}" --list
