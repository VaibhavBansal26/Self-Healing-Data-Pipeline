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
