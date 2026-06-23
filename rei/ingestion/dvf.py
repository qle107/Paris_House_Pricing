"""DVF (Demandes de Valeurs Foncières) from Etalab geo-dvf."""
from __future__ import annotations

import datetime as dt
import io

import pandas as pd

from rei.common.db import upsert_dataframe
from rei.common.io import cache_path, sha256
from rei.ingestion.base import Collector

BASE = "https://files.data.gouv.fr/geo-dvf/latest/csv"

# Residential price/area fields only.
KEEP = [
    "id_mutation", "date_mutation", "nature_mutation", "valeur_fonciere",
    "code_commune", "code_departement", "id_parcelle", "type_local",
    "surface_reelle_bati", "nombre_pieces_principales", "surface_terrain",
    "longitude", "latitude",
]

CONFLICT = ("mutation_year", "id_mutation", "id_parcelle", "type_local")


class DvfCollector(Collector):
    source_id = "dvf_transactions"
    rps = 5.0

    def commune_url(self, year: int, insee: str) -> str:
        dep = insee[:3] if insee[:2] in ("97", "98") else insee[:2]
        return f"{BASE}/{year}/communes/{dep}/{insee}.csv"

    def dept_url(self, year: int, dep: str) -> str:
        return f"{BASE}/{year}/departements/{dep}.csv.gz"

    def fetch_commune_year(self, insee: str, year: int) -> pd.DataFrame:
        url = self.commune_url(year, insee)
        try:
            resp = self.http.get(url)
        except Exception:
            self.log.warning("No DVF file for %s %s (commune may have no sales)", insee, year)
            return pd.DataFrame()
        local = cache_path(self.source_id, f"{insee}_{year}.csv")
        new_hash = None
        if local.exists():
            old_hash = sha256(local)
            local.write_bytes(resp.content)
            new_hash = sha256(local)
            if old_hash == new_hash:
                self.log.debug("Unchanged %s %s", insee, year)
        else:
            local.write_bytes(resp.content)
        df = pd.read_csv(io.BytesIO(resp.content), low_memory=False)
        cols = [c for c in KEEP if c in df.columns]
        return df[cols]

    def fetch_dept_year(self, dep: str, year: int) -> pd.DataFrame:
        """One gzipped department file (covers every commune in the department)."""
        url = self.dept_url(year, dep)
        try:
            resp = self.http.get(url)
        except Exception:
            self.log.warning("No DVF dept file for %s %s", dep, year)
            return pd.DataFrame()
        cache_path(self.source_id, f"dept_{dep}_{year}.csv.gz").write_bytes(resp.content)
        df = pd.read_csv(io.BytesIO(resp.content), compression="gzip", low_memory=False)
        cols = [c for c in KEEP if c in df.columns]
        return df[cols]

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        df = df.copy()
        df["date_mutation"] = pd.to_datetime(df["date_mutation"], errors="coerce")
        df["valeur_fonciere"] = pd.to_numeric(df["valeur_fonciere"], errors="coerce")
        df["surface_reelle_bati"] = pd.to_numeric(df.get("surface_reelle_bati"), errors="coerce")
        df = df[df["type_local"].isin(["Appartement", "Maison"])]
        df = df[(df["valeur_fonciere"] > 5_000) & (df["surface_reelle_bati"] > 8)]
        df["prix_m2"] = (df["valeur_fonciere"] / df["surface_reelle_bati"]).round(0)
        df["mutation_year"] = df["date_mutation"].dt.year.astype("Int64")
        df = df.dropna(subset=["mutation_year"])
        df = df.drop_duplicates(subset=["id_mutation", "id_parcelle", "type_local"])
        return df

    def collect(self, communes: list[str] | None = None, years: list[int] | None = None,
                departements: list[str] | None = None) -> int:
        if not years:
            y = dt.date.today().year
            years = [y - 1, y - 2]  # newest fully published millesimes
        # Department mode: one gzipped file per (dep, year) covers all its communes.
        if departements:
            frames = []
            for dep in departements:
                for year in years:
                    cleaned = self.clean(self.fetch_dept_year(dep, year))
                    self.log.info("DVF dept %s %s: %d rows", dep, year, len(cleaned))
                    if not cleaned.empty:
                        frames.append(cleaned)
            out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
            if out.empty:
                return 0
            return upsert_dataframe(out, "dvf_transactions", conflict_cols=CONFLICT)
        if not communes:
            raise ValueError("DvfCollector requires a `communes` list or `departements` list")
        frames = []
        for insee in communes:
            for year in years:
                frames.append(self.fetch_commune_year(insee, year))
        raw = pd.concat([f for f in frames if not f.empty], ignore_index=True) if frames else pd.DataFrame()
        clean = self.clean(raw)
        if clean.empty:
            return 0
        return upsert_dataframe(clean, "dvf_transactions", conflict_cols=CONFLICT)


class DvfPlusCollector(DvfCollector):
    """DVF+/DV3F aggregated mutations (Cerema)."""
    source_id = "dvf_plus_aggregated"
