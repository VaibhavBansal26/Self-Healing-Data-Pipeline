# Architecture

## Data plane
API producer publishes records to Kafka. Consumer validates payloads and applies rules-first repairs. Complex failures may enter the LangGraph decision pathway, which can retrieve prior incidents and consult operational tools. Persist valid data in PostgreSQL; quarantine unrecoverable payloads to the DLQ. Airflow runs periodic reconciliation.

## Control plane
The health checker measures Kafka, consumer, PostgreSQL, Redis, Airflow and relevant platform signals. A background auto-healer worker periodically polls health and invokes a separate decision and execution layer. Recovery adapters may start containers or repair safe conditions. Verification must re-check readiness and ideally confirm event-processing progress.

## Core distinction
**Auto-healer worker:** scheduling, polling, retries, rate limits, cooldown, and recording the monitoring cycle.

**Agent / recovery policy:** diagnosis, retrieval of past decisions, tool selection, risk classification, selection of allowlisted action, approval gate, verification and incident memory.

This distinction matters: a deterministic policy restart is not necessarily an LLM decision. Attribute decisions in traces accurately.

## State model
Use separate states for stage health (healthy/degraded/down/unknown), recovery execution (detected/planning/awaiting_approval/executing/verifying/recovered/failed) and agent activity (sleeping/active/blocked). Do not label a down stage as actively healing until an action is running.

## UI
The live stage map displays the current stage health; the recovery console retains timestamped incident history, so fast recoveries remain visible after all nodes turn green.

## Local security
A Docker socket mount effectively provides privileged control of the host Docker daemon. Restrict access; do not expose recovery endpoints publicly, and use a development machine for fault simulation.
