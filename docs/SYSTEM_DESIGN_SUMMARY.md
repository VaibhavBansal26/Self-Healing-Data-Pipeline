# Self Healing Data Pipeline Platform

## Objective

Build a production style reliability platform for streaming ecommerce order events. The platform validates incoming events, repairs safe data quality failures, routes risky failures to human approval, sends unrecoverable records to a Kafka dead letter queue, and preserves an audit trail of every problem, reason, action, and final state.

## Data Journey

```text
Producer / FastAPI
    ↓
Kafka raw_orders topic
    ↓
Python Consumer
    ↓
Transformation Layer
    ↓
Schema and Business Validation
    ↓ valid
PostgreSQL orders
    ↓ invalid
LangGraph Healing Agent
    ↓
RAG Vector Incident Memory
    ↓
OpenAI Structured Decision
    ↓
Guardrails and Risk Gate
    ↓
Repair → Verify → PostgreSQL
    ↓ risky
Human Approval Queue
    ↓ unrecoverable
Kafka DLQ
    ↓
Airflow Reconciliation + Prometheus Metrics + React Dashboard
```

## OpenAI Usage

OpenAI is used only for repair decision making. The LLM returns a structured decision and can only select from allowlisted actions such as `cast_amount_to_float`, `fill_default_currency`, `normalize_status`, `send_to_dlq`, or `manual_review`. It does not execute SQL, directly write to Kafka, or run arbitrary code.

## RAG Usage

The agent retrieves similar past incidents from vector memory before making a repair decision. This gives the agent context such as previous payload patterns, known fixes, and risky historical outcomes.

## Human Approval

High risk repairs are sent to a human approval workflow. The dashboard lets the reviewer approve for replay, reject, or close the incident as healed. The incident and replay audit trail preserve reviewer decisions.

## Logs

The React dashboard exposes action logs built from `pipeline_incidents`. Each log records:

- event id
- problem type
- reason or validation error
- selected action
- risk level
- final status
- timestamp
