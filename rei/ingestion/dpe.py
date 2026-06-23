"""ADEME DPE energy performance certificates."""
from __future__ import annotations

from rei.common.db import upsert_dataframe
from rei.ingestion.opendatasoft import OpendatasoftCollector


class DpeCollector(OpendatasoftCollector):
    source_id = "dpe_energy"
    base = "https://data.ademe.fr/data-fair/api/v1"
    dataset = "dpe-v2-logements-existants"

    def collect(self, communes: list[str] | None = None) -> int:
        where = None
        if communes:
            joined = ",".join(f'"{c}"' for c in communes)
            where = f"code_insee_ban in ({joined})"
        df = self.fetch_records(where=where, select="code_insee_ban,etiquette_dpe,surface_habitable_logement,annee_construction")
        if df.empty:
            return 0
        df = df.rename(columns={"code_insee_ban": "code_commune", "etiquette_dpe": "classe_dpe"})
        keep = [c for c in ["code_commune", "classe_dpe", "surface_habitable_logement", "annee_construction"] if c in df.columns]
        return upsert_dataframe(df[keep].reset_index(names="dpe_row_id"), "dpe", conflict_cols=("dpe_row_id",))
