# Recovery lifecycle and agent responsibility

```text
Health probe -> classify symptom -> retrieve logs/metrics and historical incidents
             -> agent/policy plan -> allowlist and approval gate
             -> execute adapter -> readiness + data-flow verification
             -> append immutable audit event -> memory update
```

The background worker performs polling and dispatch. **Do not claim an LLM chose an action unless the agent decision trace records a real model invocation.** A rules-based policy is a useful safe baseline and should be labeled as such.

## Example: consumer stopped
Expected workflow:
1. Docker probe reports container down; show consumer stage red.
2. Worker detects and creates a new incident with a unique incident ID.
3. Agent/policy selects `restart_consumer_container` subject to allowlist, cooldown, restart budget and risk level.
4. Recovery adapter attempts the restart.
5. Verify running **and readiness**; optionally enqueue an event and verify it is processed.
6. Persist `detected_at`, `action_started_at`, `verified_at`, chosen tool, policy decision, and outcome.
7. UI shows current status green and keeps a recent-recovery timeline.

Avoid restarting stateful infrastructure blindly. DLQ replay, destructive changes, database schema changes and other high-risk actions should require approval.
