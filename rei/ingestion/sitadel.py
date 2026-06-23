"""Sit@del building-permit housing series (SDES)."""
from __future__ import annotations

import io

import pandas as pd

from rei.common.db import upsert_dataframe
from rei.ingestion.base import Collector

DIDO = "https://data.statistiques.developpement-durable.gouv.fr/dido/api/v1"
DIDO_DATASET_ID = "660432ce0b8987ef5dd9465d"


class SitadelCollector(Collector):
    source_id = "sitadel_permits"
    rps = 4.0

    def latest_datafile_rid(self) -> str:
        """Resolve the newest monthly millésime's datafile id from the DiDo dataset."""
        meta = self.http.get_json(f"{DIDO}/datasets/{DIDO_DATASET_ID}")  # dataset obj carries datafiles[]
        files = meta if isinstance(meta, list) else (meta.get("data") or meta.get("datafiles") or [])
        files = [f for f in files if f.get("rid")]
        if not files:
            raise RuntimeError("No DiDo datafile for the Sitadel commune series")
        rid = max(files, key=lambda f: str(f.get("millesime", "")))["rid"]
        self.log.info("Latest Sitadel datafile rid: %s", rid)
        return rid

    def collect(self, communes: list[str] | None = None, rid: str | None = None) -> int:
        rid = rid or self.latest_datafile_rid()
        params = {"TYPE_LGT": "eq:Tous Logements"}  # all-types total, not per-type breakdown
        if communes:
            params["CODE_INSEE"] = "in:" + ",".join(communes)
        resp = self.http.get(f"{DIDO}/datafiles/{rid}/csv", params=params)
        df = pd.read_csv(io.BytesIO(resp.content), sep=";", dtype=str)
        df.columns = [c.strip().upper() for c in df.columns]
        if not {"CODE_INSEE", "ANNEE", "MOIS", "LOG_AUT"} <= set(df.columns):
            self.log.warning("Sitadel: unexpected columns %s", list(df.columns)[:12])
            return 0

        df = df.rename(columns={"CODE_INSEE": "code_commune"})
        df["code_commune"] = df["code_commune"].astype(str).str.zfill(5)
        if communes:
            df = df[df["code_commune"].isin(communes)]

        df["month"] = pd.to_datetime(
            pd.DataFrame({"year": pd.to_numeric(df["ANNEE"], errors="coerce"),
                          "month": pd.to_numeric(df["MOIS"], errors="coerce"), "day": 1}),
            errors="coerce")
        df["logements_autorises"] = pd.to_numeric(df["LOG_AUT"], errors="coerce").fillna(0)
        df = df.dropna(subset=["code_commune", "month"])

        agg = (df.groupby(["code_commune", "month"], as_index=False)
               .agg(permits=("logements_autorises", "size"),
                    logements_autorises=("logements_autorises", "sum")))
        return upsert_dataframe(agg, "permits", conflict_cols=("code_commune", "month"))


class HousingStartsCollector(SitadelCollector):
    """Logements commencés (LOG_COM) from the same DiDo file."""
    source_id = "housing_starts"
