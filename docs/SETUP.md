# Local setup

1. Install Docker Desktop with Docker Compose, Python, and Node.js.
2. Check out the full source tree.
3. Copy `.env.example` to `.env`. Add API credentials locally; never commit `.env`.
4. Start with recovery disabled to validate monitoring:
   ```bash
   docker compose up -d --build
   docker compose ps
   ./scripts/create_topics.sh
   curl http://localhost:8000/health
   curl http://localhost:8000/pipeline/health
   ```
5. Open UI at http://localhost:3000 and inspect the pipeline map.
6. To test local Docker recovery, explicitly set `ENABLE_DOCKER_STATUS=true`, `ENABLE_DOCKER_RECOVERY=true`, and `AUTO_HEAL_PIPELINE_STEPS=true` in your environment **only if you trust the local recovery service**. Recreate affected services after changing environment variables: `docker compose up -d --force-recreate data-api auto-healer`.
7. Verify Docker SDK connectivity in the API container: `docker compose exec data-api python -c "import docker; print(docker.from_env().ping())"`. The `docker` dependency must be installed by the application image.
8. Test by stopping the consumer and observing the auto-healer console and logs. Verify actual recovery using `docker compose ps consumer` and a test event.

Troubleshooting: `docker compose logs --tail=100 data-api auto-healer consumer`. Check browser network requests if the stage map reports unavailable health data.
