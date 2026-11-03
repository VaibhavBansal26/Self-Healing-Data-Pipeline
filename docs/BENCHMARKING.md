# Benchmarking

Produce 10,000 synthetic events:

```bash
PYTHONPATH=. python scripts/load_test_producer.py --events 10000 --bad-rate 0.15
```

Read current summary:

```bash
PYTHONPATH=. python scripts/benchmark_pipeline.py
```

Metrics to report in README or resume:

- events per second produced
- events processed total
- healed events total
- DLQ events total
- manual review total
- repair latency p95 from Prometheus
- database insert latency p95 from Prometheus
