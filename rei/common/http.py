"""HTTP client with retries and rate limiting."""
from __future__ import annotations

import threading
import time
from typing import Any

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config.settings import settings
from rei.common.logging import get_logger

log = get_logger(__name__)

USER_AGENT = "rei-platform/0.1 (+real-estate-intelligence; contact: data@rei.local)"


class RateLimiter:
    """Simple thread-safe token bucket: at most `rps` requests per second."""

    def __init__(self, rps: float):
        self.min_interval = 1.0 / rps if rps > 0 else 0.0
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            if now < self._next_allowed:
                time.sleep(self._next_allowed - now)
            self._next_allowed = max(now, self._next_allowed) + self.min_interval


class RetryableStatus(Exception):
    """Raised for 429/5xx so tenacity retries the call."""


class HttpClient:
    def __init__(self, rps: float | None = None, headers: dict[str, str] | None = None):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        if headers:
            self.session.headers.update(headers)
        self.limiter = RateLimiter(rps if rps is not None else settings.http_max_rps)

    @retry(
        retry=retry_if_exception_type((RetryableStatus, requests.ConnectionError, requests.Timeout)),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(6),
        reraise=True,
    )
    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        self.limiter.wait()
        kwargs.setdefault("timeout", 60)
        resp = self.session.request(method, url, **kwargs)
        if resp.status_code in (429, 500, 502, 503, 504):
            retry_after = resp.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                time.sleep(int(retry_after))
            log.warning("Retryable %s on %s", resp.status_code, url)
            raise RetryableStatus(f"{resp.status_code} {url}")
        resp.raise_for_status()
        return resp

    def get(self, url: str, **kwargs: Any) -> requests.Response:
        return self.request("GET", url, **kwargs)

    def get_json(self, url: str, **kwargs: Any) -> Any:
        return self.get(url, **kwargs).json()

    def stream_to_file(self, url: str, dest, chunk: int = 1 << 20) -> None:
        """Download a (potentially large) file to disk without loading into RAM."""
        self.limiter.wait()
        with self.session.get(url, stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(dest, "wb") as fh:
                for block in r.iter_content(chunk_size=chunk):
                    fh.write(block)
