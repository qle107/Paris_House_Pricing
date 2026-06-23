"""OFGL local-government finances by commune."""
from __future__ import annotations

from rei.common.db import upsert_dataframe
from rei.ingestion.opendatasoft import OpendatasoftCollector


class OfglCollector(OpendatasoftCollector):
    source_id = "ofgl_budgets"
    base = "https://data.ofgl.fr/api/explore/v2.1"
    dataset = "ofgl-base-communes"  # confirm current slug in catalog

    def collect(self, communes: list[str] | None = None, year: int | None = None) -> int:
        clauses = []
        if communes:
            clauses.append("insee_commune in (" + ",".join(f'"{c}"' for c in communes) + ")")
        if year:
            clauses.append(f"exer = {year}")
        where = " and ".join(clauses) if clauses else None
        df = self.fetch_records(where=where)
        if df.empty:
            return 0
        rename = {"insee_commune": "code_commune", "exer": "year"}
        df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
        keep = [c for c in df.columns if c in ("code_commune", "year", "montant", "agregat")]
        return upsert_dataframe(df[keep].reset_index(names="fin_row_id"), "municipal_finance", conflict_cols=("fin_row_id",))
