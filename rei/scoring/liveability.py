"""Family-liveability composite per IRIS (the "vivabilite familiale" lens).

Blends 0-100 sub-scores for school access, healthcare access, safety (inverse
recorded crime) and local amenities. Weights are renormalised over whatever data
is present via the same ``_wavg`` helper the institutional suite uses, and each
IRIS reports ``liveability_coverage`` (how much of the intended weight was real),
so a missing feed lowers confidence instead of faking a neutral 50. Pure pandas.
"""
from __future__ import annotations

import pandas as pd

from rei.common.logging import get_logger
from rei.scoring.indicators import percentile_score
from rei.scoring.institutional import _wavg

log = get_logger(__name__)

WEIGHTS = {"schools": 0.35, "health": 0.25, "safety": 0.25, "amenities": 0.15}


def family_liveability(features: pd.DataFrame, id_col: str = "iris_code") -> pd.DataFrame:
    """Composite from optional columns school_access_score, hospital_access_score,
    safety_score, amenity_score. Absent columns are dropped and weights renormalised."""
    idx = features.index
    parts = {
        "schools":   (features.get("school_access_score"), WEIGHTS["schools"]),
        "health":    (features.get("hospital_access_score"), WEIGHTS["health"]),
        "safety":    (features.get("safety_score"), WEIGHTS["safety"]),
        "amenities": (features.get("amenity_score"), WEIGHTS["amenities"]),
    }
    score, coverage = _wavg(parts, idx)
    out = pd.DataFrame({id_col: features[id_col].astype(str).to_numpy()})
    out["family_liveability_score"] = score
    out["liveability_coverage"] = coverage
    out["family_liveability_rank"] = score.rank(ascending=False, method="min").astype("Int64")
    return out


def _commune_safety(crime: pd.DataFrame) -> pd.DataFrame:
    """Commune safety 0-100 (higher = safer) from recorded-crime intensity."""
    d = crime.copy()
    if "code_commune" not in d.columns:
        return pd.DataFrame(columns=["code_commune", "safety_score"])
    d["code_commune"] = d["code_commune"].astype(str)
    col = next((c for c in ["taux_pour_mille", "tauxpourmille", "faits"] if c in d.columns), None)
    if col is None:
        return pd.DataFrame(columns=["code_commune", "safety_score"])
    agg = d.groupby("code_commune")[col].sum(min_count=1).reset_index()
    agg["safety_score"] = percentile_score(agg[col], -1)  # more crime -> lower safety
    return agg[["code_commune", "safety_score"]]


def run_files() -> int:
    """File-mode entry point: assemble per-IRIS family factors, write data/tables/liveability."""
    from rei.common.store import read_geo, read_table, write_table_files

    zones = read_geo("iris")
    if zones is None or zones.empty:
        log.warning("No IRIS contours in store; run iris_contours ingestion first.")
        return 0
    f = (pd.DataFrame({"iris_code": zones["iris_code"].astype(str).to_numpy(),
                       "code_commune": zones["code_commune"].astype(str).to_numpy()})
         .drop_duplicates("iris_code").reset_index(drop=True))

    acc = read_table("accessibility")
    if acc is not None and not acc.empty:
        acc = acc.copy()
        acc["iris_code"] = acc["iris_code"].astype(str)
        cols = [c for c in ["iris_code", "school_access_score", "hospital_access_score"] if c in acc.columns]
        f = f.merge(acc[cols], on="iris_code", how="left")

    crime = read_table("crime")
    if crime is not None and not crime.empty:
        saf = _commune_safety(crime)
        if not saf.empty:
            f = f.merge(saf, on="code_commune", how="left")

    # Amenities slot (BPE / commerce) — wired here for Phase 2; dropped until the feed exists.
    amen = read_table("amenities")
    if amen is not None and not amen.empty and {"iris_code", "amenity_score"} <= set(amen.columns):
        amen = amen.copy()
        amen["iris_code"] = amen["iris_code"].astype(str)
        f = f.merge(amen[["iris_code", "amenity_score"]], on="iris_code", how="left")

    out = family_liveability(f)
    log.info("Family liveability: %d IRIS | mean coverage=%.2f",
             len(out), float(out["liveability_coverage"].mean()))
    return write_table_files(out, "liveability", conflict_cols=("iris_code",))
