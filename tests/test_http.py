"""Unit tests for the rate limiter and retry behaviour (no network)."""
import time

from rei.common.http import RateLimiter


def test_rate_limiter_spaces_requests():
    rl = RateLimiter(rps=20)
    start = time.monotonic()
    for _ in range(5):
        rl.wait()
    elapsed = time.monotonic() - start
    assert elapsed >= 0.18


def test_rate_limiter_zero_rps_is_noop():
    rl = RateLimiter(rps=0)
    start = time.monotonic()
    rl.wait()
    assert time.monotonic() - start < 0.01
