# Interview Walkthrough: Self-Healing Data Pipeline Platform

## Problem
Production data pipelines fail at two levels: record-level failures such as malformed events, and pipeline-level failures such as Kafka topic loss, consumer pauses, database outages, Redis loss, LLM timeouts, Airflow failures, and DLQ replay issues.

## What this project demonstrates
- Kafka streaming ingestion and DLQ quarantine.
- PostgreSQL sink with incident and replay audit tables.
- Rules-first, LLM-second record healing.
- LangGraph Reason-Act-Verify agent workflow.
- RAG/vector memory over previous incidents and recovery decisions.
- MCP-style tool layer for operational context.
- Pipeline stage health map with green/yellow/red state.
- Agent activity state: sleeping, detecting, planning, healing, verifying, waiting for approval.
- Human approval workflow for risky actions.
- Recovery adapters for Docker, Kafka Admin, Airflow, and Kubernetes blueprint actions.
- Log diagnosis, alerting, recovery memory, and measurable pipeline healing metrics.

## Why AI agent is useful
Health checks only say what is broken. The agent chooses recovery actions using current health, log diagnosis, previous recovery memory, MCP context, risk policy, and post-action verification. It avoids blindly restarting services and can route risky actions to human approval.

## Demo flow
1. Open `http://localhost:3000`.
2. Go to Overview and inspect the stage map.
3. Go to Producer Controls and publish demo events.
4. Go to Pipeline Step Healing and run failure simulations.
5. Run Auto Heal Safe Issues.
6. Observe agent updates, colors, recovery memory, and approvals.

## Commands
```bash
./scripts/run_complete_pipeline_demo.sh
curl http://localhost:8000/pipeline/health
curl http://localhost:8000/pipeline/metrics
curl http://localhost:8000/pipeline/recovery-memory
```

## Latest UI and runtime upgrade

This version adds live Docker-aware pipeline stage health and a connected workflow visualization.

### New capabilities

- Consumer health is now based on the real `healing_consumer` Docker container, not only the Redis pause flag.
- Airflow health checks the webserver and scheduler containers plus the reconciliation database state.
- Control-plane health checks the API, frontend, metrics service, and Prometheus containers.
- The Overview page includes a connected workflow node map showing each stage and its current color.
- Every UI section includes a short explanation of what the section does, what to look for, and how to test it.
- The Overview page includes dynamic charts for stage health, record outcomes, agent traces, and recovery control signals.

### How to validate consumer-down healing

```bash
docker compose stop consumer
curl http://localhost:8000/pipeline/health
```

Expected: the `consumer` component should report `unhealthy` with `problem_type=consumer_container_down`, and the Overview stage map should show the Consumer Service node in red.

Then run:

```bash
curl -X POST http://localhost:8000/pipeline/heal
```

If `ENABLE_DOCKER_RECOVERY=true` is set and the Docker socket is mounted, the agent should start the consumer container and verify recovery.

### Required Docker recovery configuration

The `data-api` service mounts:

```yaml
- /var/run/docker.sock:/var/run/docker.sock
```

Set this in `.env` to allow real recovery:

```env
ENABLE_DOCKER_RECOVERY=true
ENABLE_DOCKER_STATUS=true
```

Without `ENABLE_DOCKER_RECOVERY=true`, the platform still detects failures but recovery actions remain safe/dry-run.
