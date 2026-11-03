# Next Level Self Healing Pipeline Features

This version adds:

1. Failure Simulator tab
2. Live event journey trace
3. Reason -> Act -> Verify trace
4. OpenAI fallback mode
5. DLQ replay workflow
6. Pressure test dashboard
7. RAG evidence visibility
8. Schema evolution
9. Better React UI and visualization

## Demo Flow

1. Open http://localhost:3000
2. Create Kafka topics.
3. Publish demo dataset or run pressure test.
4. Watch Live Journey for event movement.
5. Inspect Reason Act Verify for agent decisions.
6. Use Failure Simulator, then Pipeline Step Healing.
7. Review Human Approval and DLQ Replay.
8. Check PostgreSQL Records and Metrics.

## Added in the advanced React plus AI hardening version

- Modular React dashboard structure with pages, reusable components, API hooks, payload diff viewer, and AI coverage page.
- Rules first and LLM second repair engine.
- Redis backed LLM rate limiter and circuit breaker.
- Schema relevant payload filtering before LLM calls.
- Optional OpenTelemetry tracing hooks.
- Kafka consumer lag endpoint.
- Grafana dashboard provisioning files.
- Role based approval hooks for sensitive dashboard operations.
- Additional tests for rules, LLM safety, and Kafka lag contracts.
