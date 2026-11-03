from __future__ import annotations

import json
from typing import Any, Dict


def remember_recovery(component: str, problem_type: str, recovery_action: str, status: str, evidence: Dict[str, Any] | None = None, latency_ms: int = 0) -> Dict[str, Any]:
    try:
        from src.db import get_db_connection
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO recovery_action_memory(component,problem_type,recovery_action,status,evidence,latency_ms) VALUES(%s,%s,%s,%s,%s,%s);""", (component, problem_type, recovery_action, status, json.dumps(evidence or {}), latency_ms))
    except Exception:
        pass
    return {"component": component, "problem_type": problem_type, "recovery_action": recovery_action, "status": status}


def action_success_summary(component: str | None = None, problem_type: str | None = None) -> Dict[str, Any]:
    try:
        from src.db import get_db_connection
        where=[]; params=[]
        if component:
            where.append("component=%s"); params.append(component)
        if problem_type:
            where.append("problem_type=%s"); params.append(problem_type)
        w = "WHERE " + " AND ".join(where) if where else ""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""SELECT component, problem_type, recovery_action, status, COUNT(*) FROM recovery_action_memory {w} GROUP BY component, problem_type, recovery_action, status ORDER BY COUNT(*) DESC;""", params)
                rows=cur.fetchall()
        totals={}
        for comp, prob, act, status, count in rows:
            key=(comp,prob,act)
            totals.setdefault(key,{"component":comp,"problem_type":prob,"recovery_action":act,"healed":0,"failed":0,"manual_review":0,"other":0})
            if status in totals[key]: totals[key][status]+=count
            else: totals[key]["other"]+=count
        out=[]
        for item in totals.values():
            total=item["healed"]+item["failed"]+item["manual_review"]+item["other"]
            item["total"]=total; item["success_rate"]=round(item["healed"]/total,3) if total else None
            out.append(item)
        return {"available": True, "summaries": out}
    except Exception as exc:
        return {"available": False, "error": str(exc), "summaries": []}
