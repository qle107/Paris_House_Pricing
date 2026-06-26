"""Social housing share per commune (loi SRU inventory).

Article 55 of the loi SRU requires qualifying communes to reach 20-25% social
housing among their primary residences. Source: ``communes-et-inventaire-sru`` on
data.gouv.fr (the official annual inventory). We store the share, the legal target
and the deficit; values are broadcast to IRIS downstream by ``code_commune``
(commune grain, like the ML forecast).
"""
from __future__ import annotations

import io
import re
import unicodedata

import pandas as pd

from rei.common.db import upsert_dataframe
from rei.ingestion.base import Collector

DATAGOUV = "https://www.data.gouv.fr/api/1"
SLUG = "communes-et-inventaire-sru"
SRU_DEFAULT_TARGET = 25.0


def _slug(col: str) -> str:
    """Accent/space-insensitive header key, e.g. 'Taux de logements sociaux (%)' -> 'taux_de_logements_sociaux'."""
    c = unicodedata.normalize("NFKD", str(col)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", c.strip().lower()).strip("_")


def _first(df: pd.DataFrame, names: list[str]) -> str | None:
    return next((n for n in names if n in df.columns), None)


def normalize_sru(df: pd.DataFrame, target: float = SRU_DEFAULT_TARGET) -> pd.DataFrame:
    """Map a raw SRU inventory frame to share / target / deficit per commune.

    Header matching is accent/space-insensitive, and the share is taken from a
    precomputed rate column when present, else derived from the social-housing count
    over primary residences. Pure function, unit-tested offline.
    """
    if df.empty:
        return df
    d = df.copy()
    d.columns = [_slug(c) for c in d.columns]
    comm = _first(d, ["code_commune", "codgeo", "depcom", "code_insee", "insee", "insee_com", "numero_insee"])
    if comm is None:
        return pd.DataFrame(columns=["code_commune", "social_housing_share", "sru_target_rate", "sru_deficit_pct"])

    rate = _first(d, ["taux_sru", "taux_ls", "taux_de_logements_sociaux", "taux_de_logements_sociaux_sru",
                      "taux_lls", "part_des_logements_sociaux", "taux_de_logement_social"])
    nsoc = _first(d, ["nb_ls", "nombre_de_logements_sociaux", "inventaire_sru", "logements_sociaux",
                      "nb_logements_sociaux", "nombre_total_de_logements_sociaux", "inventaire_des_logements_sociaux"])
    nres = _first(d, ["nb_rp", "residences_principales", "nombre_de_residences_principales",
                      "nb_residences_principales", "rp", "nombre_de_residence_principale"])

    out = pd.DataFrame({"code_commune": d[comm].astype(str).str.split(".").str[0].str.zfill(5)})
    if rate is not None:
        out["social_housing_share"] = pd.to_numeric(d[rate], errors="coerce")
    elif nsoc is not None and nres is not None:
        soc = pd.to_numeric(d[nsoc], errors="coerce")
        res = pd.to_numeric(d[nres], errors="coerce").replace(0, pd.NA)
        out["social_housing_share"] = (soc / res * 100).round(2)
    else:
        return pd.DataFrame(columns=["code_commune", "social_housing_share", "sru_target_rate", "sru_deficit_pct"])

    out["sru_target_rate"] = target
    out["sru_deficit_pct"] = (target - out["social_housing_share"]).clip(lower=0).round(2)
    return out.dropna(subset=["social_housing_share"]).drop_duplicates("code_commune")


class SruCollector(Collector):
    source_id = "social_housing_sru"
    rps = 4.0

    def collect(self, communes: list[str] | None = None, **_) -> int:
        meta = self.http.get_json(f"{DATAGOUV}/datasets/{SLUG}/")
        csvs = [r for r in meta.get("resources", []) if (r.get("format") or "").lower().startswith("csv")]
        if not csvs:
            self.log.warning("No SRU CSV resource found")
            return 0
        csvs.sort(key=lambda r: r.get("last_modified", ""), reverse=True)
        raw = self.http.get(csvs[0]["url"]).content
        df = pd.read_csv(io.BytesIO(raw), sep=";", low_memory=False)
        if df.shape[1] == 1:  # wrong delimiter guess
            df = pd.read_csv(io.BytesIO(raw), sep=",", low_memory=False)
        out = normalize_sru(df)
        if communes:
            out = out[out["code_commune"].isin(communes)]
        return upsert_dataframe(out, "social_housing", conflict_cols=("code_commune",))
