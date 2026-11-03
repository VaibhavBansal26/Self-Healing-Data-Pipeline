# Measurable AI Agents

This version adds measurable AI engineering capabilities on top of the self healing data pipeline.

## What is covered

- LangSmith ready tracing through `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, and `LANGSMITH_PROJECT`.
- Multi agent comparison across:
  - detector agent
  - rules repair agent
  - conservative reviewer agent
  - LLM planner proxy agent
- Offline evaluation dataset in `evals/healing_cases.jsonl`.
- Evaluation runner in `scripts/run_healing_evals.py`.
- LLM cost tracking in `runtime/llm_costs.jsonl` with prompt tokens, completion tokens, total tokens, and estimated USD cost.
- FastAPI endpoints for dashboard and demos:
  - `GET /ai/langsmith/status`
  - `GET /ai/costs`
  - `GET /ai/evals`
  - `POST /ai/multi-agent/compare`

## Run evals

```bash
PYTHONPATH=. python scripts/run_healing_evals.py
```

## Enable LangSmith

```bash
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY=your_key
export LANGSMITH_PROJECT=self-healing-data-pipeline
```

The project still runs without LangSmith. In local mode it exposes trace readiness and local agent trace data through the API and React UI.

## Why this matters

The project is no longer just an LLM based repair demo. It can compare agent strategies, estimate cost, show accuracy, and prove that repair decisions are measurable.
