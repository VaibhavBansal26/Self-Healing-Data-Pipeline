# Integration tests

End-to-end tests for the consumer against real Kafka (KRaft), Postgres and Redis.
They use high host ports (Kafka 19092, Postgres 55442, Redis 56379) so they do not
collide with the main `docker-compose.yml` stack.

```bash
docker compose -f tests/integration/docker-compose.yml up -d --wait
RUN_INTEGRATION=1 PYTHONPATH=. pytest tests/integration -v
docker compose -f tests/integration/docker-compose.yml down -v
```

`pytest tests` ignores this directory unless `RUN_INTEGRATION=1`, because
`src.config` reads its environment at import time and the unit tests use defaults.
The OpenAI key is removed for these runs: they cover the deterministic path only.

## Chaos tests

`test_chaos.py` runs the consumer as a separate process and injects faults while
events flow. Every scenario must end with no lost events, no duplicates, and no
valid event dead-lettered because of an outage:

| Scenario | Fault |
|---|---|
| `consumer_sigkill` | `kill -9` the consumer mid-stream, restart it |
| `postgres_outage` | stop Postgres while events are published, start it again |
| `redis_outage` | stop Redis; processing must continue without retry memory |
| `kafka_restart` | restart the broker; the consumer must resume |

Recovery timings are printed in a `chaos results` section at the end of the run.
The suite takes about three minutes.
