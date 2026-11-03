# AI agent hardening upgrades

This version adds five AI engineering hardening features:

1. **Prompt injection defense and test suite**
   - Detects instruction-like payload content.
   - Filters payloads to schema-relevant fields before LLM use.
   - Exposes `/ai/security/prompt-injection` and `/ai/security/safe-context`.

2. **Semantic caching for repeated incidents**
   - Reuses verified previous decisions for similar validation failures.
   - Reduces repeat LLM calls, latency, and cost.
   - Exposes `/ai/semantic-cache` and `/ai/semantic-cache/demo`.

3. **Retrieval evaluation for vector memory**
   - Measures Precision@1, Hit@K, and MRR for incident memory retrieval.
   - Exposes `/ai/retrieval-eval`.

4. **MCP tool-use evaluation**
   - Evaluates whether the agent selects the right operational tool for Kafka, DLQ, Redis, RAG, Airflow, and Postgres problems.
   - Exposes `/ai/tool-use-eval`.

5. **Agent trajectory dashboard**
   - Shows observe, detect, retrieve memory, select tool, policy gate, and sleep/waiting steps.
   - Exposes `/ai/trajectory` and renders the timeline in the React AI Engineering tab.

Run checks:

```bash
PYTHONPATH=. pytest -q tests
cd frontend && npm install --legacy-peer-deps && npm run build
```
