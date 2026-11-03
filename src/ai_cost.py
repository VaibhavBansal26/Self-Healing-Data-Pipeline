from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

# Conservative default prices per 1M tokens. Override through env for real deployments.
MODEL_PRICES_PER_1M: Dict[str, Dict[str, float]] = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "default": {"input": 0.15, "output": 0.60},
}

@dataclass
class CostRecord:
    timestamp: float
    event_id: str
    model: str
    agent_name: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    status: str


def _price_for(model: str) -> Dict[str, float]:
    input_override = os.getenv("LLM_INPUT_PRICE_PER_1M")
    output_override = os.getenv("LLM_OUTPUT_PRICE_PER_1M")
    if input_override and output_override:
        return {"input": float(input_override), "output": float(output_override)}
    return MODEL_PRICES_PER_1M.get(model, MODEL_PRICES_PER_1M["default"])


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    price = _price_for(model)
    return round((prompt_tokens / 1_000_000) * price["input"] + (completion_tokens / 1_000_000) * price["output"], 8)


def estimate_tokens(text: Any) -> int:
    # No tokenizer dependency needed for tests. Approximation: 1 token ~= 4 chars.
    raw = text if isinstance(text, str) else json.dumps(text, default=str)
    return max(1, int(len(raw) / 4))


def _log_path() -> Path:
    path = Path(os.getenv("LLM_COST_LOG_PATH", "runtime/llm_costs.jsonl"))
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def record_llm_cost(
    event_id: str,
    model: str,
    agent_name: str,
    prompt_tokens: int,
    completion_tokens: int,
    status: str = "success",
) -> CostRecord:
    total = prompt_tokens + completion_tokens
    record = CostRecord(
        timestamp=time.time(),
        event_id=event_id or "unknown",
        model=model,
        agent_name=agent_name,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total,
        estimated_cost_usd=estimate_cost(model, prompt_tokens, completion_tokens),
        status=status,
    )
    with _log_path().open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(record)) + "\n")
    return record


def list_cost_records(limit: int = 200) -> List[Dict[str, Any]]:
    path = _log_path()
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def cost_summary() -> Dict[str, Any]:
    rows = list_cost_records(limit=10_000)
    by_agent: Dict[str, Dict[str, Any]] = {}
    total_cost = 0.0
    total_tokens = 0
    for row in rows:
        agent = row.get("agent_name", "unknown")
        by_agent.setdefault(agent, {"calls": 0, "tokens": 0, "cost_usd": 0.0})
        by_agent[agent]["calls"] += 1
        by_agent[agent]["tokens"] += int(row.get("total_tokens", 0))
        by_agent[agent]["cost_usd"] += float(row.get("estimated_cost_usd", 0.0))
        total_cost += float(row.get("estimated_cost_usd", 0.0))
        total_tokens += int(row.get("total_tokens", 0))
    for data in by_agent.values():
        data["cost_usd"] = round(data["cost_usd"], 8)
    return {
        "total_calls": len(rows),
        "total_tokens": total_tokens,
        "estimated_total_cost_usd": round(total_cost, 8),
        "by_agent": by_agent,
        "recent": rows[-25:],
    }
