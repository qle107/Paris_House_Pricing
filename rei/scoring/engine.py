"""Commune attractiveness scoring (0-100) from PostGIS materialized views."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

from rei.common.db import get_engine
from rei.common.logging import get_logger
from rei.scoring.indicators import percentile_score, risk_multiplier

log = get_logger(__name__)
WEIGHTS_FILE = Path(__file__).with_name("weights.yaml")


def load_config() -> dict:
    return yaml.safe_load(WEIGHTS_FILE.read_text(encoding="utf-8"))


def assemble_features(min_population: int = 2000, density_scores: pd.DataFrame | None = None) -> pd.DataFrame:
    """Pull mv_commune_features and derive the remaining model inputs."""
    eng = get_engine()
    f = pd.read_sql(
        "SELECT * FROM scores.mv_commune_features WHERE population >= %(p)s",
        eng, params={"p": min_population},
    )
    nsales = pd.read_sql("SELECT code_commune, n_sales_total FROM scores.mv_price_trend", eng)
    f = f.merge(nsales, on="code_commune", how="left")
    stops = pd.read_sql(
        """SELECT p.code_commune, count(DISTINCT s.stop_id) AS transport_score
           FROM gis.transit_stops s JOIN gis.parcels p
             ON ST_Within(s.geometry, p.geometry)
           GROUP BY p.code_commune""",
        eng,
    ) if _table_exists(eng, "gis", "transit_stops") else pd.DataFrame(columns=["code_commune", "transport_score"])
    f = f.merge(stops, on="code_commune", how="left")

    f["tightness"] = (f["pop_cagr"].fillna(0) + f["price_cagr_5y"].fillna(0)) / f["permits_per_1000"].replace(0, pd.NA)
    f["buildable_upside"] = f["zoning_share_au"]
    f["emp_proxy"] = f.get("pop_cagr")
    f["biz_proxy"] = pd.NA

    if density_scores is not None:
        f = f.merge(density_scores[["code_commune", "density_change_score"]], on="code_commune", how="left")
    else:
        f["density_change_score"] = pd.NA
    return f


def score(profile: str = "value_add_opportunistic", min_population: int = 2000,
          density_scores: pd.DataFrame | None = None) -> pd.DataFrame:
    cfg = load_config()
    spec = cfg["profiles"][profile]
    overlay = cfg["risk_overlay"]
    f = assemble_features(min_population, density_scores)

    total = pd.Series(0.0, index=f.index)
    for component, c in spec.items():
        src = c["source"]
        raw = f[src] if src in f.columns else pd.Series([pd.NA] * len(f), index=f.index)
        comp = percentile_score(raw, c.get("direction", 1))
        f[f"score_{component}"] = comp
        total += c["weight"] * comp

    mult = f[overlay["source"]].apply(
        lambda v: risk_multiplier(v, overlay["full_penalty_at"], overlay["min_multiplier"])
    ) if overlay["source"] in f.columns else 1.0
    f["attractiveness_score"] = (total * mult).round(1)
    f["profile"] = profile
    f["rank"] = f["attractiveness_score"].rank(ascending=False, method="min").astype("Int64")

    out_cols = ["code_commune", "name", "population", "profile", "attractiveness_score", "rank"] + \
               [c for c in f.columns if c.startswith("score_")]
    result = f[out_cols].sort_values("attractiveness_score", ascending=False)
    result.to_sql("commune_score", get_engine(), schema="scores", if_exists="replace", index=False)
    log.info("Scored %d communes (profile=%s)", len(result), profile)
    return result


def _table_exists(eng, schema: str, table: str) -> bool:
    q = ("SELECT 1 FROM information_schema.tables WHERE table_schema=%(s)s AND table_name=%(t)s")
    return not pd.read_sql(q, eng, params={"s": schema, "t": table}).empty


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="value_add_opportunistic")
    ap.add_argument("--min-population", type=int, default=2000)
    args = ap.parse_args()
    print(score(args.profile, args.min_population).head(25).to_string(index=False))
