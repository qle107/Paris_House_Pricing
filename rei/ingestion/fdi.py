"""Business France FDI projects (regional grain)."""
from __future__ import annotations

import pandas as pd

from rei.common.db import upsert_dataframe
from rei.ingestion.base import Collector


class BusinessFranceCollector(Collector):
    source_id = "fdi_businessfrance"
    rps = 1.0

    def collect(self, csv_path: str | None = None) -> int:
        if not csv_path:
            self.log.info("Provide a curated FDI CSV, or route the annual PDF via ai_agent")
            return 0
        df = pd.read_csv(csv_path)
        return upsert_dataframe(df.reset_index(names="fdi_row_id"), "fdi_projects", conflict_cols=("fdi_row_id",))
