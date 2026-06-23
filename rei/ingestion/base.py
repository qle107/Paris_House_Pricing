"""Base collector: run() wraps collect() and logs to meta.ingestion_log."""
from __future__ import annotations

from abc import ABC, abstractmethod

from rei.common.db import record_ingestion
from rei.common.http import HttpClient
from rei.common.logging import get_logger


class Collector(ABC):
    #: registry id from config/sources.yaml
    source_id: str = ""
    #: requests per second for this source
    rps: float | None = None

    def __init__(self):
        self.log = get_logger(f"ingest.{self.source_id}")
        self.http = HttpClient(rps=self.rps)

    @abstractmethod
    def collect(self, **kwargs) -> int:
        """Fetch + load. Return rows loaded. Raise on hard failure."""

    def run(self, **kwargs) -> int:
        self.log.info("START %s", self.source_id)
        try:
            rows = self.collect(**kwargs)
            record_ingestion(self.source_id, rows, "ok")
            self.log.info("DONE %s rows=%d", self.source_id, rows)
            return rows
        except Exception as exc:  # noqa: BLE001
            record_ingestion(self.source_id, 0, "error", str(exc))
            self.log.exception("FAILED %s", self.source_id)
            raise
