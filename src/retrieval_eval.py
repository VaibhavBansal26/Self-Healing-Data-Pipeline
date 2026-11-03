from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any, Dict, List

INCIDENT_MEMORY = [
    {"id":"mem_amount_string", "text":"amount field arrived as string and was repaired with cast_amount_to_float", "expected_action":"cast_amount_to_float"},
    {"id":"mem_missing_currency", "text":"currency was missing and default USD was filled after validation failure", "expected_action":"fill_default_currency"},
    {"id":"mem_bad_status", "text":"status PAY or payment_complete mapped to paid using normalize_status", "expected_action":"normalize_status"},
    {"id":"mem_negative_amount", "text":"negative payment amount is high risk and should require manual review or DLQ", "expected_action":"manual_review"},
]

EVAL_QUERIES = [
    {"query":"amount is a string 29.50, validation says number expected", "expected_memory":"mem_amount_string"},
    {"query":"record is missing currency field", "expected_memory":"mem_missing_currency"},
    {"query":"status payment_complete should become paid", "expected_memory":"mem_bad_status"},
    {"query":"negative amount cannot be safely repaired", "expected_memory":"mem_negative_amount"},
]


def _score(query: str, text: str) -> float:
    q_tokens = set(query.lower().replace("_", " ").split())
    t_tokens = set(text.lower().replace("_", " ").split())
    overlap = len(q_tokens & t_tokens) / max(1, len(q_tokens | t_tokens))
    seq = SequenceMatcher(None, query.lower(), text.lower()).ratio()
    return round((overlap * 0.65) + (seq * 0.35), 4)


def retrieve(query: str, k: int = 3) -> List[Dict[str, Any]]:
    ranked = [{**item, "score": _score(query, item["text"])} for item in INCIDENT_MEMORY]
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked[:k]


def evaluate_retrieval(k: int = 3) -> Dict[str, Any]:
    results = []
    hits_at_1 = 0
    hits_at_k = 0
    reciprocal_ranks = []
    for case in EVAL_QUERIES:
        retrieved = retrieve(case["query"], k=k)
        ids = [r["id"] for r in retrieved]
        hit1 = bool(ids and ids[0] == case["expected_memory"])
        hitk = case["expected_memory"] in ids
        hits_at_1 += int(hit1)
        hits_at_k += int(hitk)
        rank = ids.index(case["expected_memory"]) + 1 if hitk else None
        reciprocal_ranks.append(1 / rank if rank else 0)
        results.append({**case, "retrieved": retrieved, "hit_at_1": hit1, "hit_at_k": hitk, "rank": rank})
    n = len(EVAL_QUERIES)
    return {
        "cases": n,
        "k": k,
        "precision_at_1": round(hits_at_1 / n, 4),
        "hit_rate_at_k": round(hits_at_k / n, 4),
        "mean_reciprocal_rank": round(sum(reciprocal_ranks) / n, 4),
        "purpose": "Measures whether vector incident memory retrieves the right prior failure before the agent acts.",
        "results": results,
    }
