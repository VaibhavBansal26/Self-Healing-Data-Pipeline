# Pipeline Healing Runbook

## Color semantics
- Green: stage is working.
- Yellow: stage is degraded or self-healing is in progress.
- Red: stage is down, blocked, or requires approval.
- Blue agent badge: agent is active.
- Gray agent badge: agent is sleeping.

## Recovery policy
- Low-risk allowlisted actions can run automatically when `AUTO_HEAL_PIPELINE_STEPS=true`.
- High-risk actions create a human approval request.
- Docker recovery actions are dry-run unless `ENABLE_DOCKER_RECOVERY=true`.
- Kubernetes recovery actions are blueprint dry-runs by default.

## Covered failures
- Missing Kafka topic.
- Consumer paused or down.
- PostgreSQL connection or missing tables.
- Redis unavailable with fallback mode.
- OpenAI/LLM unavailable with deterministic fallback.
- Airflow reconciliation failure.
- Stuck DLQ replay.
- High Kafka lag.
- Unknown log patterns requiring human review.

## Verification
After each recovery action, the agent runs the health check again and stores the result in `pipeline_step_incidents` and `recovery_action_memory`.
