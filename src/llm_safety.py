from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class LLMGateResult:
    allowed: bool
    reason: str
    calls_in_window: int = 0


def should_call_llm(redis_client: Optional[Any], *, max_calls_per_minute: int = 20, circuit_breaker_key: str = "llm:circuit_open") -> LLMGateResult:
    """Redis backed rate limiter and circuit breaker for LLM healing.

    If Redis is unavailable, the safe behavior is to allow one call path but let
    graph fallback handling route failures to manual review.
    """
    if redis_client is None:
        return LLMGateResult(True, "Redis unavailable; allow call and rely on graph fallback.")
    try:
        if redis_client.get(circuit_breaker_key) == "true":
            return LLMGateResult(False, "LLM circuit breaker is open.")
        bucket = f"llm:rate:{int(time.time() // 60)}"
        count = int(redis_client.incr(bucket))
        redis_client.expire(bucket, 120)
        if count > max_calls_per_minute:
            return LLMGateResult(False, "LLM rate limit exceeded for this minute.", count)
        return LLMGateResult(True, "LLM call allowed.", count)
    except Exception as exc:
        return LLMGateResult(True, f"Rate limiter unavailable: {exc}")


def record_llm_failure(redis_client: Optional[Any], threshold: int = 5, open_seconds: int = 300) -> None:
    if redis_client is None:
        return
    try:
        count = int(redis_client.incr("llm:failure_count"))
        redis_client.expire("llm:failure_count", 600)
        if count >= threshold:
            redis_client.set("llm:circuit_open", "true", ex=open_seconds)
    except Exception:
        return


def sanitize_llm_context(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only schema relevant fields before LLM reasoning."""
    allowed = {"event_id", "customer_id", "amount", "currency", "status", "schema_version", "amount_cents", "order_state"}
    return {k: v for k, v in payload.items() if k in allowed}
