# Pipeline Level Self Healing

This project now separates two kinds of healing.

## 1. Record level healing

Record level healing repairs malformed events such as missing currency, invalid status, amount as a string, unsupported schema version, or unrecoverable payloads that must go to DLQ or human review.

## 2. Pipeline level healing

Pipeline level healing recovers broken pipeline steps such as Kafka topic problems, paused consumers, PostgreSQL failures, Redis degradation, missing OpenAI key, Airflow reconciliation issues, and DLQ context.

The pipeline healing agent follows a Reason Act Verify loop:

1. **Reason**: collect health signals from Kafka, PostgreSQL, Redis, OpenAI, consumer state, Airflow, DLQ count, and recent incidents.
2. **Memory**: retrieve previous pipeline step incidents and previous recovery outcomes.
3. **MCP context**: call MCP style tools such as DLQ count and recent incidents to enrich the diagnosis.
4. **Plan**: choose one allowlisted recovery action with risk and approval policy.
5. **Act**: execute safe remediations automatically, such as creating a missing Kafka topic, resuming the consumer, enabling deterministic fallback, retrying reconciliation, or entering degraded mode.
6. **Verify**: rerun the component health check and mark the recovery as healed or failed.
7. **Remember**: store the result in pipeline_step_incidents so future decisions can use it as memory.

## Why AI agent, RAG, MCP, and memory matter

A plain health check only says something is broken. The agent decides what action should be taken, whether that action is safe, whether a similar recovery failed before, which tool context matters, and whether human approval is required.

* **Agent**: plans the recovery action and performs Reason Act Verify.
* **RAG or memory**: uses previous recovery incidents and outcomes to avoid repeating failed actions.
* **MCP**: standardizes access to pipeline tools such as DLQ, incidents, replay, Redis retry state, and reconciliation.
* **Human approval**: blocks risky actions such as migrations or destructive operations.

## UI validation

Open the React app and go to **Pipeline Step Healing**.

Use:

* **Run health check** to refresh pipeline component state.
* **Auto heal safe issues** to execute allowlisted low risk actions.
* **Failure simulator** to create controlled failures.
* **Agent decision layer** to inspect diagnosis, proposed action, memory evidence, MCP context, and risk policy.
* **Pipeline healing memory** to see previous recovery actions.

Example scenarios:

* Pause consumer, then auto heal safe issues.
* Simulate OpenAI unavailable, then verify deterministic fallback.
* Delete DLQ topic, then allow the pipeline agent to recreate it.
* Stop Redis, then verify degraded mode behavior.
* Stop PostgreSQL, then verify the consumer pause and retry strategy.
