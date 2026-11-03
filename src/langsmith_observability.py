from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Dict, Iterator


def langsmith_status() -> Dict[str, Any]:
    return {
        "enabled": os.getenv("LANGSMITH_TRACING", "false").lower()
        in {"1", "true", "yes"},
        "project": os.getenv("LANGSMITH_PROJECT", "self-healing-data-pipeline"),
        "api_key_present": bool(os.getenv("LANGSMITH_API_KEY")),
        "notes": [
            "Set LANGSMITH_TRACING=true and LANGSMITH_API_KEY to enable hosted traces.",
            "The code is safe in local mode: it records structured local traces when LangSmith is not configured.",
        ],
    }


@contextmanager
def trace_run(
    name: str,
    inputs: Dict[str, Any] | None = None,
    metadata: Dict[str, Any] | None = None,
) -> Iterator[Dict[str, Any]]:
    """Optional LangSmith trace wrapper.

    This keeps the project runnable without LangSmith. When langsmith is installed
    and enabled, the LangChain/LangGraph callbacks can be configured through env.
    The returned dict is also used as a local trace envelope for tests and UI.
    """
    envelope = {
        "name": name,
        "inputs": inputs or {},
        "metadata": metadata or {},
        "outputs": {},
        "error": None,
    }
    try:
        yield envelope
    except Exception as exc:
        envelope["error"] = str(exc)
        raise
