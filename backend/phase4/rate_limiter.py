"""Phase 4: Simple rate limiting for API / LLM calls."""

from __future__ import annotations

import time
from threading import Lock
from typing import Optional


class RateLimiter:
    """
    Token-bucket style rate limiter.
    Allows up to `max_calls` calls per `window_seconds` window.
    """

    def __init__(self, max_calls: int = 10, window_seconds: float = 60.0):
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._calls: list[float] = []
        self._lock = Lock()

    def _prune(self) -> None:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        self._calls = [t for t in self._calls if t > cutoff]

    def allow(self) -> bool:
        """Return True if the call is allowed, False if rate limited."""
        with self._lock:
            self._prune()
            if len(self._calls) >= self.max_calls:
                return False
            self._calls.append(time.monotonic())
            return True

    def wait_if_needed(self) -> None:
        """
        Block until a call is allowed.
        Use sparingly; prefer allow() + return 429 in API.
        """
        while not self.allow():
            time.sleep(0.5)
