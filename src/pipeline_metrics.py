from __future__ import annotations

from typing import Any, Dict

def pipeline_healing_metrics() -> Dict[str, Any]:
    try:
        from src.db import list_pipeline_step_incidents
        rows = list_pipeline_step_incidents(limit=250)
    except Exception as exc:
        return {"available": False, "error": str(exc)}
    total=len(rows)
    healed=sum(1 for r in rows if r.get("status")=="healed")
    failed=sum(1 for r in rows if r.get("status")=="failed")
    manual=sum(1 for r in rows if r.get("status")=="manual_review")
    detected=sum(1 for r in rows if r.get("status") in {"detected","healing_started"})
    by_component={}
    for r in rows:
        c=r.get("component") or "unknown"
        by_component.setdefault(c,{"total":0,"healed":0,"failed":0,"manual_review":0})
        by_component[c]["total"]+=1
        if r.get("status") in by_component[c]: by_component[c][r.get("status")]+=1
    return {"available": True, "total_recovery_attempts": total, "healed": healed, "failed": failed, "manual_review": manual, "detected": detected, "recovery_success_rate": round(healed/total,3) if total else 1.0, "by_component": by_component}
