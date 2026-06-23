"""Opendatasoft Explore v2.1 client."""
from __future__ import annotations

import pandas as pd

from rei.ingestion.base import Collector


class OpendatasoftCollector(Collector):
    base: str = ""          # e.g. https://data.ademe.fr/data-fair/api/v1/datasets ... overridden
    dataset: str = ""
    rps = 5.0

    def fetch_records(self, where: str | None = None, select: str | None = None, limit_per_page: int = 100, max_records: int = 50_000) -> pd.DataFrame:
        rows: list[dict] = []
        offset = 0
        while offset < max_records:
            params = {"limit": limit_per_page, "offset": offset}
            if where:
                params["where"] = where
            if select:
                params["select"] = select
            payload = self.http.get_json(f"{self.base}/catalog/datasets/{self.dataset}/records", params=params)
            results = payload.get("results", [])
            rows.extend(results)
            if len(results) < limit_per_page:
                break
            offset += limit_per_page
            if offset >= 10_000:  # ODS hard offset cap; switch to export for more
                self.log.info("Hit ODS offset cap; use export endpoint for full extract")
                break
        return pd.json_normalize(rows)
