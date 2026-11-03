#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

say() { printf '\n\033[1;36m%s\033[0m\n' "$1"; }
warn() { printf '\n\033[1;33m%s\033[0m\n' "$1"; }

say "1/8 Starting AI-powered self-healing data pipeline demo"
cat > .env.demo <<'ENV'
ENABLE_DOCKER_STATUS=true
ENABLE_DOCKER_RECOVERY=true
AUTO_HEAL_PIPELINE_STEPS=true
AUTO_HEAL_INTERVAL_SECONDS=8
AUTO_HEAL_DEMO_DELAY_SECONDS=6
AUTO_HEAL_VISIBILITY_HOLD_SECONDS=120
ENABLE_LLM=true
ENV

if [ -f .env ]; then
  cp .env .env.backup.demo
  cat .env.demo >> .env
else
  cp .env.demo .env
fi

say "2/8 Building and starting Docker services"
docker compose down --remove-orphans >/dev/null 2>&1 || true
docker compose up -d --build

say "3/8 Waiting for API to become ready"
for i in {1..60}; do
  if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
    break
  fi
  sleep 2
  if [ "$i" = "60" ]; then
    warn "API did not become ready. Check: docker compose logs data-api"
    exit 1
  fi
done

say "4/8 Creating Kafka topics"
chmod +x scripts/create_topics.sh
./scripts/create_topics.sh || true

say "5/8 Initializing PostgreSQL tables"
docker exec -i healing_postgres psql -U postgres -d pipeline_db < db/init.sql >/dev/null || true

say "6/8 Publishing demo events"
python - <<'PY'
import json, urllib.request

def post(payload):
    req = urllib.request.Request(
        "http://localhost:8000/events",
        data=json.dumps({"payload": payload}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    urllib.request.urlopen(req, timeout=10).read()

cases = [
    {"event_id":"demo_valid_order","customer_id":"cust_1","amount":25.5,"currency":"USD","status":"paid"},
    {"event_id":"demo_rules_heal_amount","customer_id":"cust_2","amount":"29.50","currency":"USD","status":"paid"},
    {"event_id":"demo_missing_currency","customer_id":"cust_3","amount":40,"status":"created"},
    {"event_id":"demo_human_review","amount":75.25,"currency":"USD","status":"paid"},
]
for c in cases:
    post(c)
print("Published", len(cases), "demo events")
PY

say "7/8 Running visible pipeline failure demo: stopping consumer"
docker compose stop consumer >/dev/null
printf "Consumer stopped. Auto-healer should detect it within one interval and recover it.\n"
printf "Watch logs in another terminal: docker compose logs -f auto-healer\n"
sleep 20

say "8/8 Demo links and verification"
docker compose ps
cat <<'LINKS'

Open these:
  React dashboard:  http://localhost:3000
  Auto-healer UI:   http://localhost:3000  -> Auto-Healer Console
  FastAPI docs:     http://localhost:8000/docs
  Airflow:          http://localhost:8080  (admin/admin)
  Prometheus:       http://localhost:9090

Verify recovery:
  docker compose ps consumer
  curl http://localhost:8000/auto-healer/status
  curl http://localhost:8000/pipeline/traces

Demo flow:
  1. Auto-Healer Console: terminal-style recovery timeline
  2. Pipeline Map: current connected stage map
  3. Reason Act Verify: record-level healing
  4. Human Approval: risky cases
  5. AI Engineering: RAG, MCP, semantic cache, prompt-injection defense
LINKS
