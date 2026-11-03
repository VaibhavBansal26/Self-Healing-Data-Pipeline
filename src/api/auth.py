from __future__ import annotations

import os
from fastapi import Header, HTTPException

ROLE_ORDER = {"viewer": 0, "operator": 1, "admin": 2}


def _auth_enabled() -> bool:
    return os.getenv("REQUIRE_DASHBOARD_AUTH", "false").lower() == "true"


def require_role(required: str):
    def dependency(
        x_api_key: str | None = Header(default=None),
        x_user_role: str | None = Header(default="viewer"),
    ) -> str:
        if not _auth_enabled():
            return x_user_role or "demo-admin"
        expected_key = os.getenv("DASHBOARD_API_KEY")
        if not expected_key or x_api_key != expected_key:
            raise HTTPException(status_code=401, detail="Invalid or missing API key")
        role = x_user_role or "viewer"
        if ROLE_ORDER.get(role, -1) < ROLE_ORDER.get(required, 0):
            raise HTTPException(status_code=403, detail=f"Requires {required} role")
        return role

    return dependency
