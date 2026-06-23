"""Georisques natural/technological risk by commune."""
from __future__ import annotations

import pandas as pd

from rei.common.db import upsert_dataframe
from rei.ingestion.base import Collector

API = "https://georisques.gouv.fr/api/v1"


class GeorisquesCollector(Collector):
    source_id = "georisques"
    rps = 5.0

    def commune_risks(self, insee: str) -> dict:
        data = self.http.get_json(f"{API}/gaspar/risques", params={"code_insee": insee, "page": 1, "page_size": 100})
        risks = [r.get("libelle_risque_long") for r in data.get("data", [])]
        return {
            "code_commune": insee,
            "n_risques": len(risks),
            "inondation": any("Inondation" in (r or "") for r in risks),
            "argiles": any("argile" in (r or "").lower() for r in risks),
            "risques": "; ".join(filter(None, risks))[:1000],
        }

    def collect(self, communes: list[str] | None = None) -> int:
        if not communes:
            raise ValueError("GeorisquesCollector requires `communes`")
        rows = []
        for insee in communes:
            try:
                rows.append(self.commune_risks(insee))
            except Exception:
                self.log.warning("No risk data for %s", insee)
        df = pd.DataFrame(rows)
        return upsert_dataframe(df, "risk", conflict_cols=("code_commune",)) if not df.empty else 0
