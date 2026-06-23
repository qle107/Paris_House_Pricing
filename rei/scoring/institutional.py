"""Institutional IRIS sub-scores on top of iris_engine.

Missing inputs are dropped and weights renormalised. Coverage uses footprint
area only (no building heights).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from rei.common import store
from rei.common.logging import get_logger
from rei.scoring.indicators import percentile_score

log = get_logger(__name__)
CRS_METRIC = 2154  # Lambert-93 (metres) for areas / spatial joins

INSTITUTIONAL_W = {"appreciation": 0.30, "rental": 0.25, "value": 0.20, "development": 0.15, "risk": 0.10}
ALPHA_W = {"appreciation": 0.35, "value": 0.25, "transit": 0.20, "development": 0.10, "rental": 0.10}


def _discount_to_score(pct: pd.Series) -> pd.Series:
    """Map a €/m² discount (expected−observed, %) to 0-100: 0%→50, +20%→100, −20%→0."""
    return (50 + pct * 2.5).clip(0, 100)


def _hedonic_discount(j: pd.DataFrame) -> pd.DataFrame:
    """Hedonic discount per IRIS (no location term in the model)."""
    d = j.copy()
    d["prix_m2"] = pd.to_numeric(d.get("prix_m2"), errors="coerce")
    d["surface_reelle_bati"] = pd.to_numeric(d.get("surface_reelle_bati"), errors="coerce")
    d = d[d["prix_m2"].between(200, 25000) & (d["surface_reelle_bati"] > 8)]
    if len(d) < 50:
        return pd.DataFrame(columns=["iris_code", "observed_prix_m2", "expected_prix_m2", "discount_pct"])
    d["log_p"] = np.log(d["prix_m2"])
    feat = pd.DataFrame({
        "log_s": np.log(d["surface_reelle_bati"].clip(lower=9)),
        "rooms": pd.to_numeric(d.get("nombre_pieces_principales"), errors="coerce").fillna(0).clip(0, 12),
        "is_appt": (d.get("type_local") == "Appartement").astype(float),
        "yr": pd.to_numeric(d.get("mutation_year"), errors="coerce").fillna(0).astype(float),
    }, index=d.index)
    if "revenu_median" in d:
        rev = pd.to_numeric(d["revenu_median"], errors="coerce")
        feat["rev"] = rev.fillna(rev.median())
    try:
        from sklearn.linear_model import LinearRegression
        m = LinearRegression().fit(feat.fillna(0), d["log_p"])
        d["expected"] = np.exp(m.predict(feat.fillna(0)))
    except Exception as exc:
        log.warning("hedonic fallback (%s)", exc)
        d["expected"] = d.groupby("mutation_year")["prix_m2"].transform("median")
    g = d.groupby("iris_code").agg(observed_prix_m2=("prix_m2", "median"),
                                   expected_prix_m2=("expected", "median")).reset_index()
    g["discount_pct"] = (g["expected_prix_m2"] - g["observed_prix_m2"]) / g["expected_prix_m2"] * 100
    return g


def _iris_market(iris: pd.DataFrame) -> pd.DataFrame:
    """Per-IRIS volatility + the hedonic discount, via a point-in-polygon DVF join."""
    import geopandas as gpd
    dvf = store.read_table("dvf_transactions")
    if dvf is None or dvf.empty or "longitude" not in dvf:
        return pd.DataFrame(columns=["iris_code", "volatility", "discount_pct", "expected_prix_m2", "observed_prix_m2"])
    d = dvf.dropna(subset=["longitude", "latitude"]).copy()
    pts = gpd.GeoDataFrame(d, geometry=gpd.points_from_xy(d["longitude"], d["latitude"]), crs=4326)
    j = gpd.sjoin(pts, iris[["iris_code", "geometry"]], how="inner", predicate="within").drop(columns="index_right")
    if j.empty:
        return pd.DataFrame(columns=["iris_code", "volatility", "discount_pct", "expected_prix_m2", "observed_prix_m2"])
    ym = (j[j["prix_m2"].between(200, 25000)].groupby(["iris_code", "mutation_year"])["prix_m2"]
          .median().reset_index())
    vol = (ym.groupby("iris_code")["prix_m2"].agg(lambda s: s.std(ddof=0) / s.mean() if s.mean() else np.nan)
           .rename("volatility").reset_index())
    hed = _hedonic_discount(j)
    return vol.merge(hed, on="iris_code", how="outer")


def _iris_coverage(iris: pd.DataFrame) -> pd.DataFrame:
    """Building footprint area / parcel area per IRIS."""
    import geopandas as gpd
    parcels, buildings = store.read_geo("parcels"), store.read_geo("buildings")
    if parcels is None or parcels.empty or buildings is None or buildings.empty:
        return pd.DataFrame(columns=["iris_code", "coverage_ratio"])
    im = iris[["iris_code", "geometry"]].to_crs(CRS_METRIC)
    b = buildings.to_crs(CRS_METRIC); b["bf"] = b.geometry.area
    p = parcels.to_crs(CRS_METRIC); p["pa"] = p.geometry.area
    bj = gpd.sjoin(b.set_geometry(b.geometry.centroid)[["bf", "geometry"]], im, predicate="within")
    pj = gpd.sjoin(p.set_geometry(p.geometry.centroid)[["pa", "geometry"]], im, predicate="within")
    ba = bj.groupby("iris_code")["bf"].sum()
    pa = pj.groupby("iris_code")["pa"].sum()
    cov = (ba / pa).replace([np.inf, -np.inf], np.nan).clip(0, 1).rename("coverage_ratio").reset_index()
    return cov


def _wavg(parts: dict[str, tuple[pd.Series, float]], index) -> tuple[pd.Series, pd.Series]:
    """Weighted average over non-NaN parts; returns (score, coverage)."""
    total = pd.Series(0.0, index=index); wsum = pd.Series(0.0, index=index)
    full_w = sum(w for _, w in parts.values())
    for s, w in parts.values():
        if s is None:
            continue
        present = s.notna()
        total = total.add((s.fillna(0) * w).where(present, 0.0), fill_value=0.0)
        wsum = wsum.add(pd.Series(w, index=index).where(present, 0.0), fill_value=0.0)
    score = (total / wsum).where(wsum > 0)
    return score.round(1), (wsum / full_w).round(2)


def compute_institutional(iris_geom, base: pd.DataFrame) -> pd.DataFrame:
    """Institutional sub-scores and composites per iris_code."""
    f = base.copy()
    f["iris_code"] = f["iris_code"].astype(str)
    mkt = _iris_market(iris_geom.assign(iris_code=iris_geom["iris_code"].astype(str)))
    cov = _iris_coverage(iris_geom.assign(iris_code=iris_geom["iris_code"].astype(str)))
    f = f.merge(mkt, on="iris_code", how="left").merge(cov, on="iris_code", how="left")

    idx = f.index
    liq = f["n_sales"] if "n_sales" in f else f.get("liquidity")
    mom = f.get("price_cagr")
    supply = f.get("zoning_share_au")

    value = _discount_to_score(f["discount_pct"]) if "discount_pct" in f else None
    development = percentile_score(1 - f["coverage_ratio"], 1) if "coverage_ratio" in f and f["coverage_ratio"].notna().any() else None
    appreciation, appr_cov = _wavg({
        "momentum": (percentile_score(mom, 1) if mom is not None and mom.notna().any() else None, 0.20 + 0.15),
        "supply":   (percentile_score(supply, 1) if supply is not None and supply.notna().any() else None, 0.15),
    }, idx)

    risk, risk_cov = _wavg({
        "volatility": (percentile_score(f["volatility"], -1) if "volatility" in f and f["volatility"].notna().any() else None, 0.20),
        "liquidity":  (percentile_score(liq, 1) if liq is not None and liq.notna().any() else None, 0.15),
    }, idx)

    rental, rental_cov = _wavg({
        "liquidity": (percentile_score(liq, 1) if liq is not None and liq.notna().any() else None, 0.10),
    }, idx)

    toxicity, tox_cov = _wavg({
        "falling_price": (percentile_score(mom, -1) if mom is not None and mom.notna().any() else None, 0.30),
        "weak_liquidity": (percentile_score(liq, -1) if liq is not None and liq.notna().any() else None, 0.20),
    }, idx)

    out = pd.DataFrame({"iris_code": f["iris_code"]})
    out["inst_value"] = None if value is None else value.round(1)
    out["inst_development"] = development
    out["inst_appreciation"] = appreciation
    out["inst_risk"] = risk
    out["inst_rental"] = rental
    out["inst_toxicity"] = toxicity
    out["expected_prix_m2"] = f.get("expected_prix_m2")
    out["observed_prix_m2"] = f.get("observed_prix_m2")
    out["discount_pct"] = f.get("discount_pct")
    out["coverage_ratio"] = f.get("coverage_ratio")

    comp = {"appreciation": out["inst_appreciation"], "rental": out["inst_rental"],
            "value": out["inst_value"], "development": out["inst_development"], "risk": out["inst_risk"]}
    inst, inst_cov = _wavg({k: (comp[k], INSTITUTIONAL_W[k]) for k in INSTITUTIONAL_W}, idx)
    alpha, alpha_cov = _wavg({
        "appreciation": (out["inst_appreciation"], ALPHA_W["appreciation"]),
        "value": (out["inst_value"], ALPHA_W["value"]),
        "transit": (None, ALPHA_W["transit"]),
        "development": (out["inst_development"], ALPHA_W["development"]),
        "rental": (out["inst_rental"], ALPHA_W["rental"]),
    }, idx)
    out["institutional_score"] = inst
    out["institutional_rank"] = inst.rank(ascending=False, method="min").astype("Int64")
    out["alpha_score"] = alpha
    out["data_coverage"] = inst_cov
    log.info("Institutional scoring: %d IRIS | mean data_coverage=%.2f", len(out), float(inst_cov.mean()))
    return out
