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

# Recalibrated for IDF-wide coverage (see RANKING_METHODOLOGY_REVIEW.md). Value
# enters only trap-adjusted; toxicity / illiquidity act through the trap score and
# the quality gates rather than as positive weights; the dead "transit" term is gone.
INSTITUTIONAL_W = {"appreciation": 0.28, "rental": 0.22, "risk": 0.15,
                   "value_adj": 0.15, "development": 0.10, "liquidity": 0.10}
ALPHA_W = {"appreciation": 0.40, "rental": 0.20, "development": 0.15,
           "value_adj": 0.15, "liquidity": 0.10}

# Value-trap blend (0 = clean, 100 = severe): cheap *because* fundamentals are weak.
TRAP_W = {"weak_appreciation": 0.30, "weak_rental": 0.25, "high_toxicity": 0.20,
          "illiquidity": 0.15, "weak_risk": 0.10}


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


def value_trap_score(appreciation, rental, toxicity, liquidity, risk) -> pd.Series:
    """0 = no trap, 100 = severe. High when a location is cheap but its fundamentals
    (growth, demand, liquidity) are weak or its toxicity is high. Inputs are 0-100
    sub-scores. (Population / employment trends would strengthen this but the census
    feeds are single-year today — see RANKING_METHODOLOGY_REVIEW.md.)"""
    parts = {
        "weak_appreciation": 100 - appreciation,
        "weak_rental":       100 - rental,
        "high_toxicity":     toxicity,
        "illiquidity":       100 - liquidity,
        "weak_risk":         100 - risk,
    }
    return sum(parts[k] * w for k, w in TRAP_W.items()).round(1)


def apply_gates(score, appreciation, rental, toxicity, risk, liquidity, trap) -> pd.Series:
    """Stop one strong factor (e.g. a large discount) promoting a structurally weak
    location: hard caps, then multiplicative penalties, then a value-trap haircut."""
    s = pd.to_numeric(score, errors="coerce")
    s = s.where(appreciation >= 40, np.minimum(s, 55.0))   # weak growth cannot rank high
    s = s.where(rental >= 40, np.minimum(s, 55.0))         # weak demand cannot rank high
    s = s.mask(toxicity > 70, s * 0.85)
    s = s.mask(risk < 30, s * 0.85)
    s = s.mask(liquidity < 15, s * 0.85)                   # extremely thin market
    s = s * (1 - 0.40 * trap / 100)
    return s.round(1)


def compute_institutional(iris_geom, base: pd.DataFrame) -> pd.DataFrame:
    """Institutional sub-scores, value-trap score and gated composites per iris_code."""
    f = base.copy()
    f["iris_code"] = f["iris_code"].astype(str)
    mkt = _iris_market(iris_geom.assign(iris_code=iris_geom["iris_code"].astype(str)))
    cov = _iris_coverage(iris_geom.assign(iris_code=iris_geom["iris_code"].astype(str)))
    f = f.merge(mkt, on="iris_code", how="left").merge(cov, on="iris_code", how="left")

    # Forward signal: wire in the trained price-growth forecast (commune level).
    if "code_commune" in f.columns:
        fc = store.read_table("ml_forecast")
        if fc is not None and not fc.empty and "expected_price_cagr" in fc.columns:
            fc = fc[["code_commune", "expected_price_cagr"]].copy()
            fc["code_commune"] = fc["code_commune"].astype(str)
            f = f.merge(fc, on="code_commune", how="left")

    idx = f.index
    liq = f["n_sales"] if "n_sales" in f else f.get("liquidity")
    mom = f.get("price_cagr")
    supply = f.get("zoning_share_au")
    fwd = f.get("expected_price_cagr")
    rent = pd.to_numeric(f.get("loyer_m2"), errors="coerce") if "loyer_m2" in f else None

    liq_pct = percentile_score(liq, 1) if liq is not None else pd.Series(50.0, index=idx)

    # VALUE: hedonic discount (still location-blind — see refactor note) used only trap-adjusted.
    value = _discount_to_score(f["discount_pct"]) if "discount_pct" in f else None
    development = percentile_score(1 - f["coverage_ratio"], 1) if "coverage_ratio" in f and f["coverage_ratio"].notna().any() else None

    # APPRECIATION: forward forecast + historical momentum + supply (renormalised over present terms).
    appreciation, appr_cov = _wavg({
        "forward":  (percentile_score(fwd, 1) if fwd is not None and fwd.notna().any() else None, 0.45),
        "momentum": (percentile_score(mom, 1) if mom is not None and mom.notna().any() else None, 0.40),
        "supply":   (percentile_score(supply, 1) if supply is not None and supply.notna().any() else None, 0.15),
    }, idx)

    risk, risk_cov = _wavg({
        "volatility": (percentile_score(f["volatility"], -1) if "volatility" in f and f["volatility"].notna().any() else None, 0.20),
        "liquidity":  (percentile_score(liq, 1) if liq is not None and liq.notna().any() else None, 0.15),
    }, idx)

    # RENTAL: real rent level + transaction liquidity (was liquidity only).
    rental, rental_cov = _wavg({
        "rent":      (percentile_score(rent, 1) if rent is not None and rent.notna().any() else None, 0.60),
        "liquidity": (percentile_score(liq, 1) if liq is not None and liq.notna().any() else None, 0.40),
    }, idx)

    toxicity, tox_cov = _wavg({
        "falling_price": (percentile_score(mom, -1) if mom is not None and mom.notna().any() else None, 0.30),
        "weak_liquidity": (percentile_score(liq, -1) if liq is not None and liq.notna().any() else None, 0.20),
    }, idx)

    # Gate / trap inputs: neutral-fill so gating is deterministic.
    g_appr, g_rent, g_tox = appreciation.fillna(50.0), rental.fillna(50.0), toxicity.fillna(50.0)
    g_risk, g_liq = risk.fillna(50.0), liq_pct.fillna(50.0)
    trap = value_trap_score(g_appr, g_rent, g_tox, g_liq, g_risk)
    value_adj = (value * (1 - 0.85 * trap / 100)).round(1) if value is not None else None

    out = pd.DataFrame({"iris_code": f["iris_code"]})
    out["inst_value"] = None if value is None else value.round(1)
    out["inst_value_adj"] = value_adj
    out["inst_development"] = development
    out["inst_appreciation"] = appreciation
    out["inst_risk"] = risk
    out["inst_rental"] = rental
    out["inst_toxicity"] = toxicity
    out["value_trap_score"] = trap
    out["expected_prix_m2"] = f.get("expected_prix_m2")
    out["observed_prix_m2"] = f.get("observed_prix_m2")
    out["discount_pct"] = f.get("discount_pct")
    out["coverage_ratio"] = f.get("coverage_ratio")

    comp = {"appreciation": g_appr, "rental": g_rent, "risk": g_risk,
            "value_adj": value_adj, "development": development, "liquidity": g_liq}
    inst_base, inst_cov = _wavg({k: (comp[k], INSTITUTIONAL_W[k]) for k in INSTITUTIONAL_W}, idx)
    out["institutional_score"] = apply_gates(inst_base, g_appr, g_rent, g_tox, g_risk, g_liq, trap)
    out["institutional_rank"] = out["institutional_score"].rank(ascending=False, method="min").astype("Int64")

    alpha_base, _ = _wavg({k: (comp[k], ALPHA_W[k]) for k in ALPHA_W}, idx)
    out["alpha_score"] = apply_gates(alpha_base, g_appr, g_rent, g_tox, g_risk, g_liq, trap)
    out["data_coverage"] = inst_cov
    log.info("Institutional scoring (trap-aware): %d IRIS | mean trap=%.1f | mean coverage=%.2f",
             len(out), float(trap.mean()), float(inst_cov.mean()))
    return out
