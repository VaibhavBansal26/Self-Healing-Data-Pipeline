# Testing and benchmarking

## Unit and build checks
```bash
PYTHONPATH=. pytest -q tests
cd frontend
npm ci
npm test -- --run
npm run build
```

## Fault-injection scenarios
- Stop the Kafka consumer and verify detection, safe restart, log record, readiness and event processing.
- Stop Redis and verify degraded/fallback behavior before enabling any restart policy.
- Stop Airflow scheduler and separately webserver; verify their different effects on reconciliation and UI.
- Break database connectivity and confirm backoff, no silent loss and safe replay after recovery.
- Introduce invalid events and check deterministic rules, agent routing, human approval, DLQ and replay audit.
- Test timeout and API failure while the UI is polling: keep stale stage topology visible, distinguish unknown from healthy, and avoid a cascade of missing sections.

## Metrics to record
Detection latency, action latency, recovery latency, success and false-positive rates, Kafka lag, event loss/duplication, repair safety, RAG retrieval relevance, tool-use correctness, token cost, and agent/policy invocation counts.

Record machine specifications, sample size, workload, run commands, threshold settings and raw results. **Do not fabricate benchmark figures.**
