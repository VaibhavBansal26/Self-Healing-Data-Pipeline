"""Per-component recovery budget: bounded attempts, backoff, then escalate.

Without a budget, a service that crashes on start is restarted every healer
cycle forever. The budget allows a few spaced-out attempts inside a sliding
window; after that the component is escalated to a human until it is observed
healthy again or the window passes.

State is in-process (it lives in the API process that executes heals), so it
resets if that process restarts. Multiple API replicas would each keep their own.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Callable, Dict, List


@dataclass(frozen=True)
class BudgetDecision:
    allowed: bool
    status: str  # "allowed" | "backoff" | "exhausted"
    attempts: int
    max_attempts: int
    retry_after_seconds: float = 0.0
    first_exhaustion: bool = False  # True exactly once per exhaustion, to alert once

    def as_dict(self) -> Dict[str, object]:
        return {
            "status": self.status,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "retry_after_seconds": round(self.retry_after_seconds, 1),
        }


class HealBudget:
    def __init__(
        self,
        max_attempts: int = 3,
        window_seconds: float = 900.0,
        backoff_base_seconds: float = 10.0,
        backoff_cap_seconds: float = 300.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.backoff_base = backoff_base_seconds
        self.backoff_cap = backoff_cap_seconds
        self._clock = clock
        self._attempts: Dict[str, List[float]] = {}
        self._escalated: set[str] = set()

    @classmethod
    def from_env(cls) -> "HealBudget":
        return cls(
            max_attempts=int(os.getenv("HEAL_MAX_ATTEMPTS", "3")),
            window_seconds=float(os.getenv("HEAL_WINDOW_SECONDS", "900")),
            backoff_base_seconds=float(os.getenv("HEAL_BACKOFF_BASE_SECONDS", "10")),
            backoff_cap_seconds=float(os.getenv("HEAL_BACKOFF_CAP_SECONDS", "300")),
        )

    def _recent(self, key: str) -> List[float]:
        cutoff = self._clock() - self.window_seconds
        recent = [t for t in self._attempts.get(key, []) if t > cutoff]
        self._attempts[key] = recent
        if len(recent) < self.max_attempts:
            self._escalated.discard(key)  # budget recovered; allow a future alert
        return recent

    def _backoff(self, attempts_so_far: int) -> float:
        return min(self.backoff_cap, self.backoff_base * 2 ** (attempts_so_far - 1))

    def check(self, key: str) -> BudgetDecision:
        recent = self._recent(key)
        now = self._clock()
        if len(recent) >= self.max_attempts:
            first = key not in self._escalated
            self._escalated.add(key)
            retry_after = max(0.0, recent[0] + self.window_seconds - now)
            return BudgetDecision(
                False, "exhausted", len(recent), self.max_attempts, retry_after, first
            )
        if recent:
            ready_at = recent[-1] + self._backoff(len(recent))
            if now < ready_at:
                return BudgetDecision(
                    False, "backoff", len(recent), self.max_attempts, ready_at - now
                )
        return BudgetDecision(True, "allowed", len(recent), self.max_attempts)

    def record_attempt(self, key: str) -> None:
        self._attempts.setdefault(key, []).append(self._clock())

    def record_success(self, key: str) -> None:
        """The component was verified healthy: forget its history."""
        self._attempts.pop(key, None)
        self._escalated.discard(key)

    def snapshot(self) -> Dict[str, Dict[str, object]]:
        return {k: self.check_readonly(k) for k in list(self._attempts)}

    def check_readonly(self, key: str) -> Dict[str, object]:
        recent = self._recent(key)
        return {
            "attempts": len(recent),
            "max_attempts": self.max_attempts,
            "exhausted": len(recent) >= self.max_attempts,
        }
