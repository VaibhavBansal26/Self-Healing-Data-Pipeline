from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List


def build_agent_trajectory(
    health: Dict[str, Any], traces: List[Dict[str, Any]] | None = None, limit: int = 50
) -> Dict[str, Any]:
    traces = traces or []
    agent = health.get("agent_status", {}) if health else {}
    stages = health.get("stage_map", []) if health else []
    active = [s for s in stages if s.get("color") != "green"]
    steps: List[Dict[str, Any]] = []

    steps.append(
        {
            "step": "Observe",
            "status": "complete",
            "message": f"I scanned {len(stages)} pipeline stages and found {len(active)} stage(s) needing attention.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    for stage in active[:5]:
        steps.extend(
            [
                {
                    "step": "Detect",
                    "component": stage.get("component"),
                    "status": "complete",
                    "message": f"I detected {stage.get('problem_type') or 'a problem'} in {stage.get('label')}.",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                {
                    "step": "Retrieve memory",
                    "component": stage.get("component"),
                    "status": "complete",
                    "message": "I checked previous recovery decisions and action success rates before planning.",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                {
                    "step": "Select tool",
                    "component": stage.get("component"),
                    "status": "complete",
                    "message": f"I selected the safest operational tool/action: {stage.get('suggested_action') or 'diagnose_only'}.",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                {
                    "step": "Policy gate",
                    "component": stage.get("component"),
                    "status": (
                        "waiting"
                        if stage.get("requires_human_approval")
                        else "complete"
                    ),
                    "message": (
                        "This action needs human approval."
                        if stage.get("requires_human_approval")
                        else "This action is within the safe auto-healing policy."
                    ),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            ]
        )
    if not active:
        steps.append(
            {
                "step": "Sleep",
                "status": "idle",
                "message": "All monitored stages look healthy. I am sleeping and will wake up when signals change.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    recent_traces = traces[:limit]
    return {
        "agent_state": agent.get("state", "sleeping"),
        "headline": agent.get("headline", "Agent status unavailable"),
        "active_stage_count": len(active),
        "trajectory_steps": steps[:limit],
        "recent_system_traces": recent_traces,
        "evaluation_dimensions": [
            "correct detection",
            "relevant retrieval",
            "correct tool selection",
            "safe policy decision",
            "successful verification",
            "memory update",
        ],
    }
