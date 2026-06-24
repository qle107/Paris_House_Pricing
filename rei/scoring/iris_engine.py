"""IRIS-level scoring in file mode."""
from __future__ import annotations

import geopandas as gpd
import pandas as pd

from rei.common import store
from rei.common.logging import get_logger
from rei.scoring import files_engine as commune_engine
from rei.scoring.indicators import liquidity_density, percentile_score

log = get_logger(__name__)
CRS_METRIC = 2154

WEIGHTS = {
    "demographics": 0.15, "economics": 0.20, "housing": 0.20,
    "supply": 0.15, "accessibility": 0.15, "development": 0.15,
}

# (column, direction); missing columns score neutral 50.
COMPONENTS = {
    "demographics":  [("pop_cagr", 1), ("household_growth", 1), ("age_profile", 1)],
    "economics":     [("revenu_median", 1), ("income_growth", 1), ("employment_growth", 1)],
    "housing":       [("n_sales", 1), ("liquidity", 1), ("price_cagr", 1), ("loyer_m2", 1)],
    "supply":        [("zoning_share_au", 1), ("density_restriction", 1), ("vacancy_rate", -1)],
    "accessibility": [("dist_metro", -1), ("dist_rer", -1), ("dist_tram", -1), ("dist_gpe", -1)],
    "development":   [("parcel_buildability", 1), ("redevelopment", 1),
                      ("underused", 1), ("future_zoning", 1)],
}


def _iris_dvf(iris: gpd.GeoDataFrame, dvf: pd.DataFrame) -> pd.DataFrame:
    """Per-IRIS transaction volume, liquidity and price CAGR via point-in-polygon join."""
    d = dvf.dropna(subset=["longitude", "latitude"]).copy()
    pts = gpd.GeoDataFrame(d, geometry=gpd.points_from_xy(d["longitude"], d["latitude"]), crs=4326)
    j = gpd.sjoin(pts, iris[["iris_code", "geometry"]], how="inner", predicate="within")
    if j.empty:
        return pd.DataFrame(columns=["iris_code", "n_sales", "liquidity", "price_cagr"])
    vol = j.groupby("iris_code").size().rename("n_sales")
    priced = j[j["prix_m2"].between(200, 25000)]
    med = priced.groupby(["iris_code", "mutation_year"])["prix_m2"].median().reset_index()
    rows = []
    for code, sub in med.groupby("iris_code"):
        sub = sub.sort_values("mutation_year")
        base, last = sub.iloc[0]["prix_m2"], sub.iloc[-1]["prix_m2"]
        span = max(1, int(sub["mutation_year"].max() - sub["mutation_year"].min()))
        rows.append({"iris_code": code,
                     "price_cagr": (last / base) ** (1 / span) - 1 if base else None,
                     "median_prix_m2": last})
    feat = vol.reset_index().merge(
        pd.DataFrame(rows, columns=["iris_code", "price_cagr", "median_prix_m2"]),
        on="iris_code", how="left")
    feat["liquidity"] = feat["n_sales"]
    return feat


def _iris_zoning(iris: gpd.GeoDataFrame) -> pd.DataFrame:
    z = store.read_geo("zoning")
    if z is None or z.empty:
        return pd.DataFrame(columns=["iris_code", "zoning_share_au"])
    z = z.to_crs(CRS_METRIC)
    im = iris[["iris_code", "geometry"]].to_crs(CRS_METRIC)
    inter = gpd.overlay(im, z[["typezone", "geometry"]], how="intersection")
    if inter.empty:
        return pd.DataFrame(columns=["iris_code", "zoning_share_au"])
    inter["a"] = inter.geometry.area
    inter["au"] = inter["typezone"].fillna("").str.upper().str.startswith("AU")
    return (inter.groupby("iris_code")
            .apply(lambda s: s.loc[s["au"], "a"].sum() / s["a"].sum() if s["a"].sum() else 0.0)
            .reset_index(name="zoning_share_au"))


def assemble_iris_features() -> gpd.GeoDataFrame:
    iris = store.read_geo("iris")
    if iris is None or iris.empty:
        return gpd.GeoDataFrame()
    iris = iris.copy()
    iris["code_commune"] = iris["code_commune"].astype(str)
    f = iris[["iris_code", "iris_name", "code_commune", "geometry"]].drop_duplicates("iris_code")
    f = f.reset_index(drop=True)
    f["area_km2"] = f.to_crs(CRS_METRIC).geometry.area / 1e6   # for per-area liquidity

    dvf = store.read_table("dvf_transactions")
    if not dvf.empty:
        f = f.merge(_iris_dvf(iris, dvf), on="iris_code", how="left")
        f["sales_per_km2"] = liquidity_density(f["n_sales"], f["area_km2"])

    com = commune_engine.assemble_features()
    if not com.empty:
        com["code_commune"] = com["code_commune"].astype(str)
        keep = [c for c in ["code_commune", "pop_cagr", "revenu_median", "loyer_m2"] if c in com.columns]
        f = f.merge(com[keep], on="code_commune", how="left")

    risk = store.read_table("risk")
    if not risk.empty and "n_risques" in risk:
        risk = risk[["code_commune", "n_risques"]].copy()
        risk["code_commune"] = risk["code_commune"].astype(str)
        f = f.merge(risk, on="code_commune", how="left")

    f = f.merge(_iris_zoning(iris), on="iris_code", how="left")
    return gpd.GeoDataFrame(f, geometry="geometry", crs=iris.crs)


def _tier(pct: float) -> int:
    """Smallest opportunity bracket an IRIS falls in: 5 / 10 / 20 (%) or 0."""
    if pct >= 0.95:
        return 5
    if pct >= 0.90:
        return 10
    if pct >= 0.80:
        return 20
    return 0


def score_iris() -> gpd.GeoDataFrame:
    f = assemble_iris_features()
    if f.empty:
        log.warning("No IRIS features assembled - ingest iris_contours first")
        return f

    total = pd.Series(0.0, index=f.index)
    for comp, subs in COMPONENTS.items():
        parts = [percentile_score(f[c], d) for c, d in subs if c in f.columns and f[c].notna().any()]
        comp_score = (sum(parts) / len(parts)) if parts else pd.Series(50.0, index=f.index)
        f[f"score_{comp}"] = comp_score.round(1)
        total = total + WEIGHTS[comp] * comp_score
    f["score_total"] = total.round(1)
    f["rank"] = f["score_total"].rank(ascending=False, method="min").astype("Int64")

    hotspot = f["score_total"] + f["score_development"] + f["score_accessibility"]
    f["hotspot_tier"] = hotspot.rank(pct=True).apply(_tier).astype(int)

    try:
        from rei.scoring.institutional import compute_institutional
        f = f.merge(compute_institutional(f[["iris_code", "geometry"]].copy(), f), on="iris_code", how="left")
        log.info("Attached institutional scores to %d IRIS", len(f))
    except Exception as exc:
        log.warning("institutional scoring skipped: %s", exc)

    store.write_table_files(pd.DataFrame(f.drop(columns="geometry")), "iris_score", conflict_cols=["iris_code"])
    store.write_geo(f, "iris_scored", schema="scores", key="iris_code")
    log.info("Scored %d IRIS (file mode)", len(f))
    return f


if __name__ == "__main__":
    print(score_iris()[["iris_code", "iris_name", "score_total", "rank", "hotspot_tier"]]
          .sort_values("score_total", ascending=False).head(25).to_string(index=False))
