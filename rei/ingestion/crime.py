"""SSMSI communal crime statistics."""
from __future__ import annotations

import io

import pandas as pd

from rei.common.db import upsert_dataframe
from rei.ingestion.base import Collector

DATAGOUV = "https://www.data.gouv.fr/api/1"
SLUG = "bases-statistiques-communale-et-departementale-de-la-delinquance-enregistree-par-la-police-et-la-gendarmerie-nationales"


class CrimeCollector(Collector):
    source_id = "crime_ssmsi"
    rps = 4.0

    def collect(self, communes: list[str] | None = None) -> int:
        meta = self.http.get_json(f"{DATAGOUV}/datasets/{SLUG}/")
        csvs = [r for r in meta.get("resources", []) if "commune" in (r.get("title") or "").lower()
                and (r.get("format") or "").lower().startswith("csv")]
        if not csvs:
            self.log.warning("No communal crime CSV resource found")
            return 0
        csvs.sort(key=lambda r: r.get("last_modified", ""), reverse=True)
        resp = self.http.get(csvs[0]["url"])
        df = pd.read_csv(io.BytesIO(resp.content), sep=";", low_memory=False)
        df.columns = [c.lower() for c in df.columns]
        comm = next((c for c in ["codgeo_2024", "codgeo", "code_commune", "depcom"] if c in df.columns), None)
        if comm is None:
            return 0
        df = df.rename(columns={comm: "code_commune"})
        if communes:
            df = df[df["code_commune"].astype(str).isin(communes)]
        keep = [c for c in df.columns if c in ("code_commune", "annee", "classe", "faits", "taux_pour_mille", "tauxpourmille")]
        return upsert_dataframe(df[keep].reset_index(names="crime_row_id"), "crime", conflict_cols=("crime_row_id",))
