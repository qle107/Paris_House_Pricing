"""Education nationale school directory and IPS."""
from __future__ import annotations

from rei.common.db import upsert_dataframe
from rei.ingestion.opendatasoft import OpendatasoftCollector


class EducationCollector(OpendatasoftCollector):
    source_id = "education_ips"
    base = "https://data.education.gouv.fr/api/explore/v2.1"
    dataset = "fr-en-ips-ecoles-ap2022"  # confirm latest millesime slug in catalog

    def collect(self, communes: list[str] | None = None) -> int:
        where = None
        if communes:
            joined = ",".join(f'"{c}"' for c in communes)
            where = f"code_insee in ({joined})"
        df = self.fetch_records(where=where)
        if df.empty:
            return 0
        rename = {"code_insee": "code_commune", "ips": "ips"}
        df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
        keep = [c for c in ["code_commune", "ips", "uai", "nom_etablissement"] if c in df.columns]
        return upsert_dataframe(df[keep].drop_duplicates("uai"), "schools", conflict_cols=("uai",))
