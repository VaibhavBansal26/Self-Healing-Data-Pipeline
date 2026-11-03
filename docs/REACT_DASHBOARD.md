# React Control Dashboard

The project now uses a React + TypeScript dashboard instead of Streamlit.

## Main URLs

```text
React dashboard: http://localhost:3000
FastAPI docs:    http://localhost:8000/docs
Prometheus:      http://localhost:9090
Airflow:         http://localhost:8080
```

## What the dashboard shows

1. **Overview**
   - Orders, incidents, healed records, manual review records, failed records, DLQ count.
   - Outcome charts and recent order activity.

2. **System Design**
   - Full data journey from producer/API to Kafka, consumer, transformation, validation, LangGraph agent, RAG memory, human approval, DLQ, Airflow, and Prometheus.

3. **Producer & Consumer**
   - Publish full demo dataset.
   - Publish individual failure scenarios.
   - Publish custom JSON.
   - Pause or resume the consumer using Redis state.

4. **Transformation Playground**
   - Paste raw JSON and preview deterministic transformations before Kafka ingestion.

5. **Agent Trace and Human Approval**
   - Inspect failed payloads, error messages, healing action, risk level, original payload, healed payload, and agent steps.
   - Approve for replay, reject, or close as healed.

6. **RAG Memory**
   - Search similar incidents from vector memory to see what context the healing agent can use.

7. **Action Logs**
   - View problem, reason, selected action, risk, and final status for each incident.

8. **API Playground**
   - Direct links to FastAPI Swagger, health, summary, and architecture JSON.

## Start

```bash
docker compose down
docker compose build data-api frontend
docker compose up -d
```

Open:

```text
http://localhost:3000
```

## Why React instead of Streamlit

React is better for this project because it supports a production style dashboard with richer control flows, reusable components, modern charts, custom journey visualization, and a UI that looks more like a real internal platform used by infrastructure or data platform teams.
