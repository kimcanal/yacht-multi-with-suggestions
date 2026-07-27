"""Small dependency-free fixed-window limiter for expensive public APIs."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class SlidingWindowRateLimiter:
    def __init__(self, limit: int, window_seconds: float):
        self.limit = limit
        self.window_seconds = window_seconds
        self._lock = threading.RLock()
        self._hits = defaultdict(deque)

    def allow(self, key: str, now: float | None = None) -> tuple[bool, int]:
        now = time.time() if now is None else now
        with self._lock:
            hits = self._hits[key]
            threshold = now - self.window_seconds
            while hits and hits[0] <= threshold:
                hits.popleft()
            if len(hits) >= self.limit:
                retry_after = max(1, int(hits[0] + self.window_seconds - now) + 1)
                return False, retry_after
            hits.append(now)
            return True, 0
