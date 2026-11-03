from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from src.trace_events import trace_event, list_trace_events

API_BASE_URL = os.getenv("AUTO_HEAL_API_BASE_URL", "http://data-api:8000").rstrip("/")
INTERVAL_SECONDS = int(os.getenv("AUTO_HEAL_INTERVAL_SECONDS", "8"))
AUTO_HEAL_ENABLED = os.getenv("AUTO_HEAL_PIPELINE_STEPS", "true").lower() == "true"
# These two values are intentionally UI-focused. Healing can be too fast to see,
# so we hold a visible state long enough for the dashboard to show the agent cycle.
DEMO_DELAY_SECONDS = int(os.getenv("AUTO_HEAL_DEMO_DELAY_SECONDS", "0"))
VISIBILITY_HOLD_SECONDS = int(os.getenv("AUTO_HEAL_VISIBILITY_HOLD_SECONDS", "90"))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _meta(row: Dict[str, Any]) -> Dict[str, Any]:
    raw = row.get("metadata") or {}
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {"raw": raw}
    return raw


def log(message: str, **metadata: Any) -> None:
    payload = {"message": message, "auto_heal_enabled": AUTO_HEAL_ENABLED, **metadata}
    print(
        f"[auto-healer] {_utc_now()} {message} {json.dumps(metadata, default=str)}",
        flush=True,
    )
    trace_event("auto_healer", "background_loop", "info", metadata=payload)


def _request_json(
    method: str, path: str, body: Dict[str, Any] | None = None, timeout: int = 20
) -> Dict[str, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{API_BASE_URL}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def _unhealthy_components(health: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for component in health.get("components", []):
        action = component.get("suggested_action")
        if component.get("status") != "healthy" and action and action != "none":
            rows.append(component)
    return rows


def _safe_summary(unhealthy: List[Dict[str, Any]]) -> List[str]:
    return [
        f"{c.get('component')}:{c.get('problem_type')}→{c.get('suggested_action')}"
        for c in unhealthy
    ]


def run_once() -> Dict[str, Any]:
    """Run one auto-healing cycle.

    The background worker is intentionally not the brain. It is the watcher that
    calls the same /pipeline/heal endpoint used by the UI. The agent/policy layer
    still decides safe vs risky, executes allowlisted recovery, verifies, and logs.
    """
    started = time.time()
    if not AUTO_HEAL_ENABLED:
        log(
            "Auto-heal is disabled. The background agent is sleeping.", state="disabled"
        )
        return {"state": "disabled", "message": "AUTO_HEAL_PIPELINE_STEPS is false"}

    trace_event(
        "auto_healer",
        "detect",
        "started",
        metadata={
            "message": "I am checking pipeline health in the background.",
            "api_base_url": API_BASE_URL,
        },
    )
    health = _request_json("GET", "/pipeline/health", timeout=12)
    unhealthy = _unhealthy_components(health)

    if not unhealthy:
        trace_event(
            "auto_healer",
            "sleep",
            "healthy",
            latency_ms=int((time.time() - started) * 1000),
            metadata={
                "message": "All stages healthy. Agent sleeping.",
                "state": "sleeping",
            },
        )
        log(
            "All monitored stages are healthy. Background agent is sleeping.",
            state="sleeping",
        )
        return {
            "state": "sleeping",
            "message": "All monitored stages are healthy",
            "unhealthy": [],
        }

    summary = _safe_summary(unhealthy)
    trace_event(
        "auto_healer",
        "detect",
        "unhealthy_detected",
        metadata={
            "state": "detecting",
            "message": "I found an unhealthy pipeline stage and I am preparing a safe recovery plan.",
            "unhealthy": unhealthy,
            "summary": summary,
        },
    )
    trace_event(
        "auto_healer",
        "plan",
        "agent_active",
        metadata={
            "state": "planning",
            "message": "I am using policy, previous recovery memory, MCP context, and health signals to decide the next action.",
            "summary": summary,
            "demo_delay_seconds": DEMO_DELAY_SECONDS,
        },
    )
    log(
        "Detected unhealthy stages. Starting safe auto-heal.",
        state="healing",
        unhealthy=summary,
    )

    if DEMO_DELAY_SECONDS > 0:
        trace_event(
            "auto_healer",
            "visible_delay",
            "waiting_before_heal",
            metadata={
                "state": "healing_visible_delay",
                "message": f"I am holding the healing state for {DEMO_DELAY_SECONDS} seconds so the UI can show what is happening.",
                "summary": summary,
            },
        )
        time.sleep(DEMO_DELAY_SECONDS)

    trace_event(
        "auto_healer",
        "heal",
        "started",
        metadata={
            "state": "healing",
            "message": "I am now executing safe allowlisted recovery through /pipeline/heal.",
            "actions": summary,
        },
    )
    heal = _request_json("POST", "/pipeline/heal", timeout=45)
    trace_event(
        "auto_healer",
        "heal",
        "completed",
        latency_ms=int((time.time() - started) * 1000),
        metadata={
            "state": "healing_completed",
            "message": "The recovery command finished. I am verifying the pipeline state now.",
            "response": heal,
            "summary": summary,
        },
    )

    verify = _request_json("GET", "/pipeline/health", timeout=12)
    still_unhealthy = _unhealthy_components(verify)
    final_state = "recovered" if not still_unhealthy else "needs_attention"
    trace_event(
        "auto_healer",
        "verify",
        final_state,
        latency_ms=int((time.time() - started) * 1000),
        metadata={
            "state": final_state,
            "message": (
                "Recovery verified. The affected stages are healthy again."
                if final_state == "recovered"
                else "Some stages still need attention or approval."
            ),
            "initial_unhealthy_summary": summary,
            "remaining_unhealthy": still_unhealthy,
            "hold_seconds": VISIBILITY_HOLD_SECONDS,
        },
    )
    trace_event(
        "auto_healer",
        "ui_latch",
        "recently_recovered" if final_state == "recovered" else "recently_attention",
        metadata={
            "state": (
                "recently_recovered"
                if final_state == "recovered"
                else "needs_attention"
            ),
            "message": (
                "I just completed an automatic safe recovery. This event will stay visible briefly even though the live map is green again."
                if final_state == "recovered"
                else "I attempted recovery, but some stages still need attention."
            ),
            "initial_unhealthy_summary": summary,
            "remaining_unhealthy": still_unhealthy,
            "hold_seconds": VISIBILITY_HOLD_SECONDS,
            "cycle_latency_ms": int((time.time() - started) * 1000),
        },
    )
    log(
        "Auto-heal cycle finished.",
        state=final_state,
        remaining=[c.get("component") for c in still_unhealthy],
    )

    return {
        "state": final_state,
        "message": (
            "Safe auto-heal cycle completed"
            if final_state == "recovered"
            else "Some stages still need attention or approval"
        ),
        "initial_unhealthy": unhealthy,
        "heal_response": heal,
        "final_health": verify,
        "remaining_unhealthy": still_unhealthy,
    }


def main() -> None:
    log(
        "Background auto-healer loop started.",
        state="started",
        interval_seconds=INTERVAL_SECONDS,
        api_base_url=API_BASE_URL,
        demo_delay_seconds=DEMO_DELAY_SECONDS,
        visibility_hold_seconds=VISIBILITY_HOLD_SECONDS,
    )
    while True:
        try:
            run_once()
        except urllib.error.URLError as exc:
            trace_event(
                "auto_healer",
                "background_loop",
                "api_unavailable",
                metadata={
                    "error": str(exc),
                    "api_base_url": API_BASE_URL,
                    "state": "api_unavailable",
                },
            )
            print(f"[auto-healer] {_utc_now()} API unavailable: {exc}", flush=True)
        except Exception as exc:
            trace_event(
                "auto_healer",
                "background_loop",
                "error",
                metadata={"error": str(exc), "state": "error"},
            )
            print(f"[auto-healer] {_utc_now()} error: {exc}", flush=True)
        time.sleep(INTERVAL_SECONDS)


def auto_healer_status(limit: int = 80) -> Dict[str, Any]:
    traces = [
        t
        for t in list_trace_events(limit=limit * 4)
        if t.get("trace_name") == "auto_healer"
    ][:limit]
    latest = traces[0] if traces else None
    now = datetime.now(timezone.utc)

    # Prefer a recent active/recovery cycle over a later "sleep" trace so the UI
    # does not miss fast recoveries.
    active_statuses = {
        "unhealthy_detected",
        "agent_active",
        "waiting_before_heal",
        "started",
        "completed",
        "recovered",
        "needs_attention",
        "recently_recovered",
        "recently_attention",
    }
    recent_cycle = []
    recent_recovery = None
    for row in traces:
        created = _parse_dt(row.get("created_at"))
        if created and now - created <= timedelta(seconds=VISIBILITY_HOLD_SECONDS):
            if (
                row.get("stage")
                in {"detect", "plan", "visible_delay", "heal", "verify", "ui_latch"}
                or row.get("status") in active_statuses
            ):
                recent_cycle.append(row)
                if row.get("status") in {
                    "recovered",
                    "recently_recovered",
                    "needs_attention",
                    "recently_attention",
                }:
                    recent_recovery = (
                        row if recent_recovery is None else recent_recovery
                    )

    latest_meta = _meta(latest) if latest else {}
    active_meta = _meta(recent_cycle[0]) if recent_cycle else latest_meta

    if recent_cycle:
        statuses = {r.get("status") for r in recent_cycle[:6]}
        if (
            "waiting_before_heal" in statuses
            or "started" in statuses
            or "agent_active" in statuses
            or "unhealthy_detected" in statuses
        ):
            state = "healing_visible"
            latest_message = (
                active_meta.get("message")
                or "The background agent is actively detecting, planning, or healing."
            )
        elif recent_recovery:
            recovery_meta = _meta(recent_recovery)
            state = (
                recovery_meta.get("state")
                or recent_recovery.get("status")
                or "recently_recovered"
            )
            latest_message = (
                recovery_meta.get("message")
                or "The background agent recently completed a recovery."
            )
        else:
            state = active_meta.get("state") or "recent_activity"
            latest_message = (
                active_meta.get("message")
                or "Recent background auto-healer activity is available."
            )
    else:
        state = (
            latest_meta.get("state")
            or (latest or {}).get("status")
            or "waiting_for_first_cycle"
        )
        latest_message = (
            latest_meta.get("message")
            or "Waiting for the background auto-healer to write its first trace."
        )

    return {
        "enabled": AUTO_HEAL_ENABLED,
        "interval_seconds": INTERVAL_SECONDS,
        "demo_delay_seconds": DEMO_DELAY_SECONDS,
        "visibility_hold_seconds": VISIBILITY_HOLD_SECONDS,
        "api_base_url": API_BASE_URL,
        "state": state,
        "latest_message": latest_message,
        "latest_event": latest,
        "recent_activity": traces,
        "current_cycle_events": recent_cycle[:20],
        "recent_recovery_event": recent_recovery,
        "what_it_does": [
            "Every few seconds it calls /pipeline/health.",
            "If every stage is healthy, it logs that the agent is sleeping.",
            "If a safe allowlisted issue appears, it calls /pipeline/heal automatically.",
            "It verifies the stage after recovery and writes traces for the UI timeline.",
            "Fast recoveries are kept visible for a short hold window so you can see what happened.",
            "Risky or unverifiable actions stay in Human Approval instead of being executed blindly.",
        ],
    }


if __name__ == "__main__":
    main()
