"""INSEE collectors via Melodi API."""
from __future__ import annotations

import json

import pandas as pd

from rei.common.db import upsert_dataframe
from rei.ingestion.base import Collector

MELODI = "https://api.insee.fr/melodi"              # data endpoint: /melodi/data/{ds}
CATALOG_URL = "https://api.insee.fr/melodi/V2/catalog/all"


class _MelodiBase(Collector):
    rps = 0.5  # 30 requests / minute

    #: catalog keyword(s) for dataset discovery
    catalog_keywords: tuple[str, ...] = ()
    #: fallback dataset id
    default_dataset_id: str = ""
    #: target table in schema core
    target_table: str = ""
    conflict_cols: tuple[str, ...] = ("geo_code", "year", "indicator")
    #: extra /data query filters
    query_filters: dict = {}
    #: prefer dataset ids containing these tokens
    prefer_id_tokens: tuple[str, ...] = ()

    def discover_dataset_id(self) -> str:
        """Use the known id when set, else resolve it from the Melodi catalog by keyword."""
        if self.default_dataset_id:
            return self.default_dataset_id
        catalog = self.http.get_json(CATALOG_URL)
        if isinstance(catalog, dict):  # the list may be wrapped under an unknown key
            datasets = next((v for v in catalog.values() if isinstance(v, list)), [])
        else:
            datasets = catalog
        matches = [
            ds for ds in datasets if isinstance(ds, dict)
            and all(k.lower() in json.dumps(ds, ensure_ascii=False).lower() for k in self.catalog_keywords)
        ]
        if not matches:
            self.log.warning("No Melodi dataset matched %s", self.catalog_keywords)
            return ""
        best = max(matches, key=lambda ds: sum(
            t.upper() in str(ds.get("id", "")).upper() for t in self.prefer_id_tokens))
        ds_id = best.get("id") or best.get("identifier") or ""
        self.log.info("Resolved dataset id %s", ds_id)
        return ds_id

    def fetch_observations(self, dataset_id: str, params: dict | None = None) -> pd.DataFrame:
        """Page through a Melodi dataset and return a tidy observations frame."""
        params = dict(params or {})
        params.setdefault("maxResult", 5000)
        url = f"{MELODI}/data/{dataset_id}"
        rows: list[dict] = []
        page = 0
        while url:
            payload = self.http.get_json(url, params=params if page == 0 else None)
            for obs in payload.get("observations", []):
                dims = obs.get("dimensions", {})
                measures = obs.get("measures", {})
                value = next(iter(measures.values()), {}) if isinstance(measures, dict) else {}
                rows.append({**dims, "value": value.get("value") if isinstance(value, dict) else value})
            nxt = (payload.get("paging") or {}).get("next")
            url, page = (nxt, page + 1) if nxt else (None, page)
            if page > 1000:  # hard safety stop
                break
        self.log.info("Fetched %d observations from %s", len(rows), dataset_id)
        return pd.DataFrame(rows)

    def normalize(self, df: pd.DataFrame) -> pd.DataFrame:  # pragma: no cover
        raise NotImplementedError

    def collect(self, communes: list[str] | None = None, dataset_id: str | None = None,
                departements: list[str] | None = None, **_) -> int:
        ds_id = dataset_id or self.discover_dataset_id()
        if not ds_id:
            return 0
        # Department mode: one bulk sweep of the dataset, filtered to commune rows in
        # the requested departments. Far fewer requests than per-commune for all of IDF.
        if departements:
            raw = self.fetch_observations(ds_id, dict(self.query_filters))
            tidy = self.normalize(raw) if not raw.empty else pd.DataFrame()
            if not tidy.empty:
                tidy = tidy[tidy["geo_code"].str.len() == 5]
                tidy = tidy[tidy["geo_code"].str[:2].isin(set(departements))]
            if tidy is not None and not tidy.empty:
                return upsert_dataframe(tidy, self.target_table, self.conflict_cols)
            self.log.warning("Bulk fetch returned no commune rows for %s; "
                             "falling back to per-commune", departements)
            communes = _communes_in_departements(departements)
        frames = []
        for insee in communes or []:
            df = self.fetch_observations(ds_id, {"GEO": _geo_value(insee), **self.query_filters})
            if not df.empty:
                frames.append(df)
        raw = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        if raw.empty:
            return 0
        tidy = self.normalize(raw)
        return upsert_dataframe(tidy, self.target_table, self.conflict_cols)


class InseePopulationCollector(_MelodiBase):
    source_id = "insee_population"
    catalog_keywords = ("populations",)
    default_dataset_id = "DS_POPULATIONS_REFERENCE"
    query_filters = {"POPREF_MEASURE": "PMUN"}
    target_table = "demographics"

    def normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        geo = _first_col(df, ["GEO", "geo", "REF_AREA", "CODGEO"])
        time = _first_col(df, ["TIME_PERIOD", "TIME", "ANNEE"])
        out = pd.DataFrame({
            "geo_code": _clean_geo(df[geo]),
            "year": pd.to_numeric(df[time], errors="coerce").astype("Int64"),
            "indicator": "population",
            "value": pd.to_numeric(df["value"], errors="coerce"),
        })
        return out.dropna(subset=["geo_code", "year"])


class InseeEmploymentCollector(_MelodiBase):
    source_id = "insee_employment"
    catalog_keywords = ("emploi", "population active")
    default_dataset_id = "DS_RP_EMPLOI_LR"
    target_table = "employment"

    def normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        geo = _first_col(df, ["GEO", "CODGEO", "REF_AREA"])
        time = _first_col(df, ["TIME_PERIOD", "ANNEE"])
        return pd.DataFrame({
            "geo_code": df[geo].astype(str),
            "year": pd.to_numeric(df[time], errors="coerce").astype("Int64"),
            "indicator": "emploi_total",
            "value": pd.to_numeric(df["value"], errors="coerce"),
        }).dropna(subset=["geo_code", "year"])


class InseeIncomeCollector(_MelodiBase):
    source_id = "insee_income"
    catalog_keywords = ("filosofi",)
    prefer_id_tokens = ("DISP", "COM")          # the commune-level disposable-income series
    default_dataset_id = ""                       # resolved from the live catalog (id varies by build)
    target_table = "income"
    # FiLoSoFi: keep median standard of living only (MED_SL).
    median_tokens = ("MED_SL", "MEDIANE")

    def normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        geo = _first_col(df, ["GEO", "CODGEO", "REF_AREA"])
        time = _first_col(df, ["TIME_PERIOD", "ANNEE"])
        df = df.copy()
        # Filter on measure columns (not geo/time/value); nuniq==1 dropped all rows before.
        meas_cols = [c for c in df.columns if c not in (geo, time, "value")]
        if meas_cols:
            tag = df[meas_cols].astype(str).agg(" ".join, axis=1).str.upper()
            mask = tag.str.contains("|".join(self.median_tokens), regex=True, na=False)
            if not mask.any():
                self.log.warning("FiLoSoFi: no median measure matched; codes seen=%s",
                                 sorted(set(tag))[:30])
            df = df[mask]
        out = pd.DataFrame({
            "geo_code": _clean_geo(df[geo]),
            "year": pd.to_numeric(df[time], errors="coerce").astype("Int64"),
            "indicator": "revenu_median_uc",
            "value": pd.to_numeric(df["value"], errors="coerce"),
        }).dropna(subset=["geo_code", "year", "value"])
        return out.drop_duplicates(["geo_code", "year"])


class InseeMigrationCollector(_MelodiBase):
    source_id = "insee_migration"
    catalog_keywords = ("migration", "residentielle")
    default_dataset_id = "DS_RP_MIGRATION"
    target_table = "migration"
    conflict_cols = ("geo_code", "year", "indicator")

    def normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        geo = _first_col(df, ["GEO", "CODGEO", "REF_AREA"])
        time = _first_col(df, ["TIME_PERIOD", "ANNEE"])
        return pd.DataFrame({
            "geo_code": df[geo].astype(str),
            "year": pd.to_numeric(df[time], errors="coerce").astype("Int64"),
            "indicator": "solde_migratoire",
            "value": pd.to_numeric(df["value"], errors="coerce"),
        }).dropna(subset=["geo_code", "year"])


class InseeHouseholdCollector(InseeMigrationCollector):
    source_id = "insee_household_formation"
    catalog_keywords = ("menages",)
    default_dataset_id = "DS_RP_MENAGES"
    target_table = "households"


class BpeCollector(InseeMigrationCollector):
    source_id = "bpe_equipements"
    catalog_keywords = ("base permanente", "equipements")
    default_dataset_id = "DS_BPE"
    target_table = "amenities"


def _first_col(df: pd.DataFrame, candidates: list[str]) -> str:
    for c in candidates:
        if c in df.columns:
            return c
    others = [c for c in df.columns if c != "value"]
    if not others:
        raise KeyError(f"None of {candidates} present and no dimension columns found")
    return others[0]


def _clean_geo(s: pd.Series) -> pd.Series:
    """Melodi GEO values arrive like '2025-ARM-75101' or 'COM-92012'; reduce to the
    bare INSEE code ('75101', '92012') so it joins to code_commune downstream."""
    return (s.astype(str)
            .str.replace(r"^\d{4}-", "", regex=True)
            .str.replace(r"^(ARM|COM|DEP|REG)-", "", regex=True)
            .str.strip())


def _communes_in_departements(departements: list[str]) -> list[str]:
    """Commune codes for the given departments, read from the ingested boundaries."""
    from rei.common.store import read_geo
    g = read_geo("communes")
    if g is None or g.empty or "code_commune" not in g.columns:
        return []
    codes = g["code_commune"].astype(str)
    deps = set(departements)
    return sorted(codes[codes.str[:2].isin(deps)].unique().tolist())


def _geo_value(insee: str) -> str:
    """Melodi geo selector: Paris/Lyon/Marseille arrondissements use ARM, other communes COM."""
    arr = insee.startswith("751") or insee.startswith("6938") or insee.startswith("132")
    return f"ARM-{insee}" if arr else f"COM-{insee}"
