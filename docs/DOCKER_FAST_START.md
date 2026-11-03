# Fast Docker Startup

The app services now use `Dockerfile.app` and `requirements-app.txt` so Python dependencies are installed once at image build time instead of every time containers start.

## First run after this change

```bash
docker compose down
docker compose build data-api
# dashboard, consumer, and metrics reuse the same self-healing-app image
docker compose up -d
```

## Normal run after the first build

```bash
docker compose up -d
```

## Rebuild after changing requirements-app.txt or Dockerfile.app

```bash
docker compose build --no-cache data-api
docker compose up -d
```

## Endpoints

Dashboard: http://127.0.0.1:8501

Data API docs: http://127.0.0.1:8000/docs

Prometheus: http://127.0.0.1:9090

Metrics: http://127.0.0.1:9108/metrics


## React frontend

The production dashboard is served by the `frontend` service on port `3000`.

```bash
docker compose build data-api frontend
docker compose up -d
```

Open:

```text
http://localhost:3000
```

The older Streamlit dashboard has been replaced by a React + TypeScript UI.
