#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[1/8] Starting Docker Compose stack"
docker compose up -d --build

echo "[2/8] Waiting for API"
for i in {1..60}; do
  if curl -fsS http://localhost:8000/health >/dev/null; then break; fi
  sleep 2
  if [ "$i" = "60" ]; then echo "API did not start"; exit 1; fi
done

echo "[3/8] Creating Kafka topics"
chmod +x scripts/create_topics.sh || true
./scripts/create_topics.sh || true

echo "[4/8] Initial health"
curl -fsS http://localhost:8000/pipeline/health | python -m json.tool | head -80

echo "[5/8] Publish demo data and pressure sample"
curl -fsS -X POST http://localhost:8000/events/demo | python -m json.tool || true
curl -fsS -X POST "http://localhost:8000/events/pressure-test?total=100" | python -m json.tool || true

echo "[6/8] Simulate pipeline failures"
for s in pause_consumer openai_unavailable redis_unavailable airflow_dag_failed; do
  echo "--- scenario: $s"
  curl -fsS -X POST http://localhost:8000/failure-simulator/run -H 'Content-Type: application/json' -d "{\"scenario\":\"$s\"}" | python -m json.tool || true
done

echo "[7/8] Run safe self healing"
curl -fsS -X POST http://localhost:8000/pipeline/heal/safe | python -m json.tool | head -120 || true

echo "[8/8] Final dashboard URLs"
echo "React:   http://localhost:3000"
echo "API:     http://localhost:8000/docs"
echo "Prom:    http://localhost:9090"
echo "Health:  http://localhost:8000/pipeline/health"
