"""Commune scoring from Parquet/GeoParquet files (no database)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from rei.common import store
from rei.common.logging import get_logger
from rei.scoring.indicators import percentile_score, risk_multiplier

log = get_logger(__name__)
WEIGHTS_FILE = Path(__file__).with_name("weights.yaml")
CRS_METRIC = 2154


def _price_features(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["code_commune", "median_prix_m2_last", "price_cagr_5y", "n_sales_total"]
    if df.empty:
        return pd.DataFrame(columns=cols)
    df = df.copy()
    df["code_commune"] = df["code_commune"].astype(str)
    g = (df[df["prix_m2"].between(200, 25000)]
         .groupby(["code_commune", "mutation_year"])["prix_m2"].median().reset_index())
    rows = []
    for code, sub in g.groupby("code_commune"):
        sub = sub.sort_values("mutation_year")
        last = sub.iloc[-1]["prix_m2"]
        base = sub[sub["mutation_year"] >= sub["mutation_year"].max() - 5].iloc[0]["prix_m2"]
        span = max(1, sub["mutation_year"].max() - sub["mutation_year"].min())
        cagr = (last / base) ** (1 / span) - 1 if base else None
        rows.append({"code_commune": code, "median_prix_m2_last": last,
                     "price_cagr_5y": cagr, "n_sales_total": int(df[df.code_commune == code].shape[0])})
    feat = pd.DataFrame(rows, columns=cols)
    feat["code_commune"] = feat["code_commune"].astype(str)
    return feat


def _long_cagr(df: pd.DataFrame, indicator: str, out: str) -> pd.DataFrame:
    if df.empty or "indicator" not in df:
        return pd.DataFrame(columns=["code_commune", out])
    d = df[df["indicator"] == indicator].rename(columns={"geo_code": "code_commune"})
    rows = []
    for code, sub in d.groupby("code_commune"):
        sub = sub.sort_values("year")
        if len(sub) >= 2 and sub.iloc[0]["value"]:
            span = max(1, int(sub.iloc[-1]["year"] - sub.iloc[0]["year"]))
            rows.append({"code_commune": code,
                         out: (sub.iloc[-1]["value"] / sub.iloc[0]["value"]) ** (1 / span) - 1})
    return pd.DataFrame(rows, columns=["code_commune", out])


def _zoning_share_au() -> pd.DataFrame:
    gdf = store.read_geo("zoning")
    if gdf is None or gdf.empty:
        return pd.DataFrame(columns=["code_commune", "zoning_share_au"])
    g = gdf.to_crs(CRS_METRIC)
    g["area"] = g.geometry.area
    g["is_au"] = g["typezone"].fillna("").str.upper().str.startswith("AU")
    agg = g.groupby("code_commune").apply(
        lambda s: s.loc[s["is_au"], "area"].sum() / s["area"].sum() if s["area"].sum() else 0.0
    ).reset_index(name="zoning_share_au")
    return agg


def assemble_features(min_population: int = 0) -> pd.DataFrame:
    communes = store.read_geo("communes")
    if communes is not None and not communes.empty:
        f = communes[["code_commune", "name"]].drop_duplicates("code_commune").copy()
    else:
        demo = store.read_table("demographics")
        codes = demo["geo_code"].unique() if not demo.empty else []
        f = pd.DataFrame({"code_commune": codes, "name": None})
    if f.empty:
        return f
    f["code_commune"] = f["code_commune"].astype(str)

    f = f.merge(_price_features(store.read_table("dvf_transactions")), on="code_commune", how="left")
    f = f.merge(_long_cagr(store.read_table("demographics"), "population", "pop_cagr"), on="code_commune", how="left")

    inc = store.read_table("income")
    if not inc.empty:
        inc = (inc[inc["indicator"] == "revenu_median_uc"].rename(columns={"geo_code": "code_commune"})
               .groupby("code_commune")["value"].max().reset_index(name="revenu_median"))
        f = f.merge(inc, on="code_commune", how="left")

    demo = store.read_table("demographics")
    if not demo.empty:
        pop = (demo[demo["indicator"] == "population"].rename(columns={"geo_code": "code_commune"})
               .sort_values("year").groupby("code_commune")["value"].last().reset_index(name="population"))
        f = f.merge(pop, on="code_commune", how="left")

    permits = store.read_table("permits")
    if not permits.empty and "population" in f:
        recent = permits.copy()
        recent["month"] = pd.to_datetime(recent["month"], errors="coerce")
        cut = pd.Timestamp.utcnow().tz_localize(None) - pd.DateOffset(months=36)
        recent = recent[recent["month"] >= cut].groupby("code_commune")["logements_autorises"].sum().reset_index()
        f = f.merge(recent, on="code_commune", how="left")
        f["permits_per_1000"] = 1000 * f["logements_autorises"] / f["population"]

    rents = store.read_table("rents")
    if not rents.empty:
        col = next((c for c in rents.columns if "loypredm2" in c or "loyer" in c), None)
        if col:
            r = rents[["code_commune", col]].rename(columns={col: "loyer_m2"}).copy()
            # Source stores rent with European comma decimals ("18,00") -> parse to float.
            r["loyer_m2"] = pd.to_numeric(r["loyer_m2"].astype(str).str.replace(",", ".", regex=False),
                                          errors="coerce")
            f = f.merge(r, on="code_commune", how="left")

    risk = store.read_table("risk")
    if not risk.empty and "n_risques" in risk:
        f = f.merge(risk[["code_commune", "n_risques"]], on="code_commune", how="left")

    f = f.merge(_zoning_share_au(), on="code_commune", how="left")

    up = store.read_geo("parcel_upside")
    if up is not None and not up.empty:
        agg = up.groupby("code_commune")["buildable_upside_m2"].sum().reset_index(name="buildable_upside")
        f = f.merge(agg, on="code_commune", how="left")

    if {"pop_cagr", "price_cagr_5y", "permits_per_1000"} <= set(f.columns):
        _pop = pd.to_numeric(f["pop_cagr"], errors="coerce").fillna(0.0)
        _pcg = pd.to_numeric(f["price_cagr_5y"], errors="coerce").fillna(0.0)
        _perm = pd.to_numeric(f["permits_per_1000"], errors="coerce").replace(0, float("nan"))
        f["tightness"] = (_pop + _pcg) / _perm
    f["emp_proxy"] = f.get("pop_cagr")
    f["transport_score"] = f.get("transport_score")
    if "population" in f and min_population:
        f = f[(f["population"].fillna(0) >= min_population) | f["population"].isna()]
    return f


def score(profile: str = "value_add_opportunistic", min_population: int = 0) -> pd.DataFrame:
    cfg = yaml.safe_load(WEIGHTS_FILE.read_text(encoding="utf-8"))
    spec, overlay = cfg["profiles"][profile], cfg["risk_overlay"]
    f = assemble_features(min_population)
    if f.empty:
        log.warning("No commune features assembled — ingest some sources first")
        return f

    total = pd.Series(0.0, index=f.index)
    for comp, c in spec.items():
        src = c["source"]
        raw = f[src] if src in f.columns else pd.Series([pd.NA] * len(f), index=f.index)
        sc = percentile_score(raw, c.get("direction", 1))
        f[f"score_{comp}"] = sc
        total += c["weight"] * sc

    if overlay["source"] in f.columns:
        mult = f[overlay["source"]].apply(lambda v: risk_multiplier(v, overlay["full_penalty_at"], overlay["min_multiplier"]))
    else:
        mult = 1.0
    f["attractiveness_score"] = (total * mult).round(1)
    f["profile"] = profile
    f["rank"] = f["attractiveness_score"].rank(ascending=False, method="min").astype("Int64")

    cols = ["code_commune", "name", "profile", "attractiveness_score", "rank"] + \
           [c for c in f.columns if c.startswith("score_")] + \
           [c for c in ["population", "median_prix_m2_last", "price_cagr_5y", "pop_cagr"] if c in f.columns]
    result = f[cols].sort_values("attractiveness_score", ascending=False)
    store.write_table_files(result, "commune_score", conflict_cols=["code_commune"])
    log.info("Scored %d communes (file mode, profile=%s)", len(result), profile)
    return result


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="value_add_opportunistic")
    args = ap.parse_args()
    print(score(args.profile).head(25).to_string(index=False))
