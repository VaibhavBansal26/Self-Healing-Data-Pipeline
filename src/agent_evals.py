from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from src.multi_agent import compare_agents


def load_eval_cases(path: str = "evals/healing_cases.jsonl") -> List[Dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    cases = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            cases.append(json.loads(line))
    return cases


def evaluate_agents(path: str = "evals/healing_cases.jsonl") -> Dict[str, Any]:
    cases = load_eval_cases(path)
    if not cases:
        return {"cases": 0, "accuracy": 0.0, "results": [], "by_agent": {}}

    rows = []
    by_agent: Dict[str, Dict[str, Any]] = {}
    winner_correct = 0
    for case in cases:
        comparison = compare_agents(case["payload"], case.get("error_message", "validation failed"))
        expected = case["expected_action"]
        winner = comparison["winner"]
        if winner["action"] == expected:
            winner_correct += 1
        for result in comparison["results"]:
            agent = result["agent_name"]
            by_agent.setdefault(agent, {"correct": 0, "total": 0, "cost_usd": 0.0, "latency_ms": 0.0})
            by_agent[agent]["total"] += 1
            by_agent[agent]["cost_usd"] += float(result.get("estimated_cost_usd", 0.0))
            by_agent[agent]["latency_ms"] += float(result.get("latency_ms", 0.0))
            if result["action"] == expected:
                by_agent[agent]["correct"] += 1
        rows.append({
            "case_id": case.get("case_id"),
            "description": case.get("description"),
            "expected_action": expected,
            "winner_action": winner["action"],
            "winner_agent": winner["agent_name"],
            "correct": winner["action"] == expected,
            "comparison": comparison,
        })
    for stats in by_agent.values():
        stats["accuracy"] = round(stats["correct"] / stats["total"], 4) if stats["total"] else 0.0
        stats["cost_usd"] = round(stats["cost_usd"], 8)
        stats["avg_latency_ms"] = round(stats["latency_ms"] / stats["total"], 2) if stats["total"] else 0.0
        del stats["latency_ms"]
    return {
        "cases": len(cases),
        "winner_accuracy": round(winner_correct / len(cases), 4),
        "by_agent": by_agent,
        "results": rows,
    }
