from __future__ import annotations

from typing import Any, Dict
from src.config import PII_FIELDS

MASK = "***MASKED***"


def redact_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Mask PII before sending payload context to the LLM."""
    redacted: Dict[str, Any] = {}
    for key, value in payload.items():
        if key.lower() in PII_FIELDS:
            redacted[key] = MASK
        elif isinstance(value, dict):
            redacted[key] = redact_payload(value)
        else:
            redacted[key] = value
    return redacted
