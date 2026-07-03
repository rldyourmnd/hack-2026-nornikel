from __future__ import annotations

import threading
import time

# Client-side pacing for shared provider quotas (Yandex AI Studio: 10 RPS on
# embeddings, 10 concurrent generations). Retry-with-backoff alone loses
# against a saturated quota — observed live: all attempts landed in 429 when
# many threads fired concurrently. Pacing at the source is the fix; retries
# stay only for residual races with other consumers of the same folder.


class RateLimiter:
    """Process-wide min-interval limiter (one queue per named quota)."""

    def __init__(self, requests_per_second: float) -> None:
        self._interval = 1.0 / max(requests_per_second, 0.1)
        self._lock = threading.Lock()
        self._next_slot = 0.0

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            wait = self._next_slot - now
            self._next_slot = max(self._next_slot, now) + self._interval
        if wait > 0:
            time.sleep(wait)


_registry: dict[str, RateLimiter] = {}
_registry_lock = threading.Lock()


def get_limiter(name: str, requests_per_second: float) -> RateLimiter:
    """Named singleton limiter: every caller of one quota shares one queue."""
    with _registry_lock:
        limiter = _registry.get(name)
        if limiter is None:
            limiter = RateLimiter(requests_per_second)
            _registry[name] = limiter
        return limiter
