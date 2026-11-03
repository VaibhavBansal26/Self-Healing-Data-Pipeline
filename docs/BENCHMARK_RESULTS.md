# Benchmark Results

These are local benchmark targets and example outputs for validating the project on a laptop with Docker Compose. Replace the sample values with your measured values after running the scripts.

## How to run

```bash
PYTHONPATH=. python scripts/load_test_producer.py
PYTHONPATH=. python scripts/pressure_test_api.py
PYTHONPATH=. python scripts/benchmark_pipeline.py
```

## Sample benchmark summary

| Test | Workload | Expected result |
|---|---:|---|
| API pressure test | 500 requests across health/summary/AI endpoints | 0 critical failures, p95 below local target |
| Producer load test | 10,000 synthetic Kafka events | consumer processes valid events, DLQ captures invalid records |
| Auto-heal recovery | consumer stopped once | detected and recovered automatically within one auto-heal interval + demo delay |
| Redis recovery | redis stopped once | detected and restarted automatically if Docker recovery is enabled |
| Prompt injection suite | built-in malicious payloads | suspicious payloads filtered from LLM context |
| Retrieval evaluation | built-in RAG cases | Precision@K, hit rate, and MRR reported |
| MCP tool-use evaluation | built-in tool routing cases | tool selection accuracy reported |

## Metrics to capture

| Metric | Source |
|---|---|
| `pipeline_recovery_attempts_total` | Prometheus / metrics endpoint |
| `pipeline_recovery_success_total` | Prometheus / metrics endpoint |
| `events_processed_total` | consumer metrics |
| `events_healed_total` | consumer metrics |
| `events_sent_to_dlq_total` | consumer metrics |
| recovery latency | `/pipeline/traces` |
| agent trajectory duration | `/ai/trajectory` |
| auto-healer state | `/auto-healer/status` |

## Local benchmark notes

- Docker Desktop resource limits strongly affect results.
- Airflow startup can dominate first-run latency.
- LLM-backed cases vary by model latency and network conditions.
- For interview demos, emphasize measured local behavior and the architecture tradeoffs rather than claiming cloud-scale performance.
