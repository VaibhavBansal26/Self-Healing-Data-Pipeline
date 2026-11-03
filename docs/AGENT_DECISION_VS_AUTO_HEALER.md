# Auto-Healer Worker vs Agent Decision Layer

This project intentionally separates background monitoring from autonomous decision making.

## Auto-healer worker

File: `src/auto_healer_loop.py`

The worker is a scheduler and monitor. It does not decide risky actions by itself.

Responsibilities:

1. Poll `/pipeline/health` every few seconds.
2. Detect unhealthy components.
3. Call `/pipeline/heal` when safe auto-heal mode is enabled.
4. Write visible trace events for the terminal-style UI.
5. Keep recent recoveries visible long enough for demos.

## Agent decision layer

Files: `src/pipeline_health.py`, `src/pipeline_learning.py`, `src/recovery_adapters/*`, `src/trace_events.py`

The agent/policy layer decides what action should happen.

Inputs:

- Health signal
- Component risk level
- Suggested recovery action
- Previous recovery memory
- MCP-style tool context
- Human approval policy

Outputs:

- Safe action auto-executed
- Risky action sent to approval
- Recovery trace
- Verification result
- Updated memory

## Example: consumer down

```text
Auto-healer detects consumer_container_down
  ↓
Calls /pipeline/heal
  ↓
Agent decision layer sees restart_consumer_container is safe
  ↓
Docker recovery adapter starts healing_consumer
  ↓
Verifier checks Docker state
  ↓
Trace and recovery memory are written
```

## Example: risky DLQ replay

```text
Auto-healer detects DLQ issue
  ↓
Calls /pipeline/heal
  ↓
Agent decision layer marks replay as risky
  ↓
Human approval request is created
  ↓
Operator approves or rejects
  ↓
Approved action is executed and audited
```
