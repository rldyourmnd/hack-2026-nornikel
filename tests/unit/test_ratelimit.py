from __future__ import annotations

import time

from nornikel_kg.adapters.ratelimit import RateLimiter, get_limiter


def test_rate_limiter_spaces_requests() -> None:
    limiter = RateLimiter(requests_per_second=50)  # 20ms interval
    started = time.monotonic()
    for _ in range(5):
        limiter.acquire()
    elapsed = time.monotonic() - started
    assert elapsed >= 0.07  # 4 intervals of 20ms minimum


def test_get_limiter_is_shared_per_name() -> None:
    assert get_limiter("test-shared", 5) is get_limiter("test-shared", 99)
