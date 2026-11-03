#!/usr/bin/env bash
cat <<'URLS'
React Dashboard:        http://localhost:3000
Auto-Healer Console:    http://localhost:3000  -> Auto-Healer Console
FastAPI Docs:           http://localhost:8000/docs
Airflow UI:             http://localhost:8080   admin/admin
Prometheus:             http://localhost:9090

Useful APIs:
  curl http://localhost:8000/pipeline/health
  curl http://localhost:8000/auto-healer/status
  curl http://localhost:8000/pipeline/traces
  curl http://localhost:8000/ai/trajectory
  curl http://localhost:8000/ai/ops-observatory
URLS
