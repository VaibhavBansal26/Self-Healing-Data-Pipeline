# AI Engineering Coverage

This project demonstrates more than a basic LLM integration. It is designed as an AI reliability layer for streaming data infrastructure.

## Covered

1. LangGraph agent workflow
   The healing flow is modeled as retrieve memory, diagnose, approval gate, repair, and verify.

2. Reason Act Verify pattern
   Every bad event has a trace showing the problem, evidence, selected action, and verification result.

3. RAG over incident memory
   Previous incidents are stored and retrieved from vector memory so similar failures can guide future repairs.

4. MCP tool layer
   The agent accesses infrastructure through an MCP compatible tool abstraction instead of hardcoded service calls.

5. Structured output
   LLM decisions are constrained to approved repair actions and fields.

6. Rules first, LLM second
   Deterministic repair rules handle obvious cases before the LLM is used, reducing cost, risk, and latency.

7. Human in the loop approval
   High risk repairs are routed to manual approval using the LangGraph interrupt pattern.

8. Guardrails and safety
   The project uses an action allowlist, risk levels, confidence thresholds, PII redaction, schema relevant payload filtering, and safe fallback behavior.

9. LLM reliability controls
   A Redis backed rate limiter and circuit breaker can prevent LLM overload and force manual review when needed.

10. AI observability
   The React dashboard shows agent traces, RAG evidence, decisions, risk levels, and repair outcomes.

## Next AI improvements

1. Add LangSmith tracing for prompt, tool, and graph run inspection.
2. Add an offline evaluation dataset for healing decisions.
3. Add prompt injection test cases with malicious payload fields.
4. Add retrieval quality metrics for vector memory.
5. Split the agent into detector, repairer, verifier, and reviewer roles for multi agent comparison.
6. Add few shot incident examples ranked by similarity and outcome quality.
7. Track LLM cost per incident and compare against rules based repair.
8. Add automatic prompt regression tests before deployment.
