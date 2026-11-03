# Pipeline Step Healing

The project now supports two levels of self healing.

## 1. Record level healing

A single Kafka event fails validation. The LangGraph agent retrieves similar incidents with RAG, reasons over the validation error and guardrails, chooses a safe action, verifies the healed payload, then inserts the record or routes it to human review/DLQ.

## 2. Pipeline step healing

A data flow component fails. The pipeline healing agent checks component health, diagnoses root cause, executes allowlisted recovery actions, verifies the component again, and logs a pipeline step incident.

Components monitored:

* Kafka topics: `raw_orders` and `dead_letter_events`
* Consumer pause state
* PostgreSQL connectivity and required tables
* Redis connectivity
* OpenAI configuration
* Airflow reconciliation state

Safe recovery actions:

* Create missing Kafka topics
* Resume paused consumer
* Enable deterministic LLM fallback mode
* Continue without Redis retry memory during Redis degradation
* Pause consumer when PostgreSQL is down
* Run reconciliation

Risky actions, such as database migrations, offset resets, and destructive replays, are routed to human approval.

## Reason → Act → Verify

Reason: inspect logs, health checks, metrics, schema state, and RAG incident memory.

Act: execute one allowlisted recovery action only.

Verify: rerun the same health check after the action before marking the incident as healed.

## Demo endpoints

```bash
curl http://localhost:8000/pipeline/health
curl -X POST http://localhost:8000/pipeline/heal/safe
curl http://localhost:8000/pipeline/incidents
```

Heal one component:

```bash
curl -X POST http://localhost:8000/pipeline/heal/component \
  -H "Content-Type: application/json" \
  -d '{"component":"kafka","action":"create_missing_topic","approve_risky":false}'
```
