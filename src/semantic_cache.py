from __future__ import annotations

import hashlib
import json
import time
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

_CACHE: List[Dict[str, Any]] = []


def normalize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    keys = ["amount", "currency", "status", "schema_version", "order_state", "amount_cents"]
    return {k: str(payload.get(k, "<missing>")).lower().strip() for k in keys if k in payload or k in {"amount", "currency", "status"}}


def cache_key(payload: Dict[str, Any], error_message: str) -> str:
    normalized = {"payload": normalize_payload(payload), "error": error_message[:200].lower()}
    raw = json.dumps(normalized, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def similarity(a: Dict[str, Any], b: Dict[str, Any], error_a: str = "", error_b: str = "") -> float:
    sa = json.dumps(normalize_payload(a), sort_keys=True) + " " + error_a[:200].lower()
    sb = json.dumps(normalize_payload(b), sort_keys=True) + " " + error_b[:200].lower()
    return round(SequenceMatcher(None, sa, sb).ratio(), 4)


def put_semantic_decision(payload: Dict[str, Any], error_message: str, decision: Dict[str, Any], verified: bool = True) -> Dict[str, Any]:
    item = {
        "key": cache_key(payload, error_message),
        "payload_signature": normalize_payload(payload),
        "error_message": error_message[:500],
        "decision": decision,
        "verified": verified,
        "created_at_epoch": time.time(),
        "hits": 0,
    }
    _CACHE.append(item)
    return item


def find_cached_decision(payload: Dict[str, Any], error_message: str, threshold: float = 0.91) -> Optional[Dict[str, Any]]:
    best: Optional[Dict[str, Any]] = None
    best_score = 0.0
    for item in _CACHE:
        if not item.get("verified"):
            continue
        score = similarity(payload, item.get("payload_signature", {}), error_message, item.get("error_message", ""))
        if score > best_score:
            best = item
            best_score = score
    if best and best_score >= threshold:
        best["hits"] = int(best.get("hits", 0)) + 1
        return {**best, "similarity": best_score, "cache_hit": True, "human_update": "I found a similar verified incident in semantic cache, so I can avoid another LLM call."}
    return None


def seed_demo_cache() -> None:
    if _CACHE:
        return
    put_semantic_decision(
        {"event_id":"seed_1", "customer_id":"cust", "amount":"29.50", "currency":"USD", "status":"paid"},
        "amount should be a valid number",
        {"action":"cast_amount_to_float", "confidence":0.97, "source":"semantic_cache_seed"},
    )
    put_semantic_decision(
        {"event_id":"seed_2", "customer_id":"cust", "amount":10, "status":"created"},
        "currency field required",
        {"action":"fill_default_currency", "confidence":0.94, "source":"semantic_cache_seed"},
    )


def semantic_cache_summary() -> Dict[str, Any]:
    seed_demo_cache()
    total_hits = sum(int(i.get("hits", 0)) for i in _CACHE)
    return {
        "entries": len(_CACHE),
        "total_hits": total_hits,
        "purpose": "Reuse verified decisions for similar repeated incidents to lower latency and LLM cost.",
        "threshold": 0.91,
        "recent": _CACHE[-10:],
    }


def semantic_cache_demo() -> Dict[str, Any]:
    seed_demo_cache()
    test = {"event_id":"new_1", "customer_id":"cust2", "amount":"30.00", "currency":"USD", "status":"paid"}
    hit = find_cached_decision(test, "amount should be a valid number", threshold=0.80)
    return {"query": test, "cache_result": hit, "summary": semantic_cache_summary()}
