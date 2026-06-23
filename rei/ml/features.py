"""Point-in-time feature panel for the price-growth ML model.

Leakage fix: features are derived only from transactions on or before each
base year, while the target is the forward return measured strictly after it.
A training row therefore never sees data from its own prediction window. The
same `features_asof` builds both the training panel and the serving row, so
train-time and serve-time inputs are computed identically (no train/serve skew).

Structural feeds (income, risk, IPS, zoning share) are intentionally NOT joined
here: `scores.mv_commune_features` is a single current snapshot with no year
dimension, so joining it onto historical rows is exactly the lookahead bug this
module replaces. Re-add them through `features_asof` once point-in-time
snapshots exist (see Roadmap in the README).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from rei.common.db import get_engine

# Point-in-time features, all derived from DVF transaction history.
FEATURE_COLS = [
    "price_level_log",   # log median EUR/m2 at the base year
    "price_cagr_3y",     # trailing 3-year CAGR of median EUR/m2
    "price_cagr_5y",     # trailing 5-year CAGR (NaN where history is short)
    "liquidity_log",     # log1p trailing transaction count over the window
    "volatility",        # coeff. of variation of annual median over the window
    "trend_accel",       # last YoY minus prior YoY (momentum change)
]

PRICE_MIN, PRICE_MAX = 200, 25000


def load_price_long(engine=None) -> pd.DataFrame:
    """Per (commune, year): median EUR/m2 and transaction count, in-band only.

    Works in both backends: Parquet via `store` in file mode, SQL otherwise.
    """
    from rei.common import store
    if store.using_files():
        return _price_long_from_files(store.read_table("dvf_transactions"))
    eng = engine or get_engine()
    df = pd.read_sql(
        """SELECT code_commune,
                  mutation_year AS year,
                  percentile_cont(0.5) WITHIN GROUP (ORDER BY prix_m2) AS median_prix_m2,
                  count(*) AS n_sales
           FROM core.dvf_transactions
           WHERE prix_m2 BETWEEN 200 AND 25000
           GROUP BY code_commune, mutation_year""",
        eng,
    )
    df["code_commune"] = df["code_commune"].astype(str)
    return df.sort_values(["code_commune", "year"]).reset_index(drop=True)


def _price_long_from_files(dvf: pd.DataFrame) -> pd.DataFrame:
    """File-mode equivalent of the load_price_long SQL aggregation."""
    cols = ["code_commune", "year", "median_prix_m2", "n_sales"]
    if dvf is None or dvf.empty:
        return pd.DataFrame(columns=cols)
    d = dvf.copy()
    d["code_commune"] = d["code_commune"].astype(str)
    d["prix_m2"] = pd.to_numeric(d.get("prix_m2"), errors="coerce")
    d["year"] = pd.to_numeric(d.get("mutation_year"), errors="coerce")
    d = d[d["prix_m2"].between(PRICE_MIN, PRICE_MAX) & d["year"].notna()]
    if d.empty:
        return pd.DataFrame(columns=cols)
    d["year"] = d["year"].astype(int)
    g = (d.groupby(["code_commune", "year"])
           .agg(median_prix_m2=("prix_m2", "median"), n_sales=("prix_m2", "size"))
           .reset_index())
    return g.sort_values(["code_commune", "year"]).reset_index(drop=True)


def _cagr(first: float | None, last: float | None, years: int) -> float:
    if first is None or last is None or years <= 0:
        return np.nan
    if not (first > 0) or not (last > 0):
        return np.nan
    return (last / first) ** (1.0 / years) - 1.0


def features_asof(price_long: pd.DataFrame, base_year: int, window: int = 5) -> pd.DataFrame:
    """Point-in-time features for every commune, using only year <= base_year.

    The anchor is each commune's most recent year at or before `base_year`, so a
    commune with a one-year gap still gets features. For training rows the base
    year is always present (a target requires it), so the anchor equals it.
    """
    hist = price_long[price_long["year"] <= base_year]
    if hist.empty:
        return pd.DataFrame(columns=["code_commune", "base_year", *FEATURE_COLS])

    rows: list[dict] = []
    for code, g in hist.groupby("code_commune", sort=False):
        g = g.sort_values("year")
        by_year = dict(zip(g["year"].astype(int), g["median_prix_m2"].astype(float)))
        anchor = int(g["year"].iloc[-1])
        level = by_year[anchor]

        win = g[g["year"] > base_year - window]
        liquidity = float(win["n_sales"].sum())
        wv = win["median_prix_m2"].astype(float)
        volatility = float(wv.std(ddof=0) / wv.mean()) if len(wv) >= 2 and wv.mean() else np.nan

        yoy_last = (level / by_year[anchor - 1] - 1.0) if (anchor - 1) in by_year else np.nan
        yoy_prev = (
            by_year[anchor - 1] / by_year[anchor - 2] - 1.0
            if (anchor - 1) in by_year and (anchor - 2) in by_year
            else np.nan
        )
        accel = yoy_last - yoy_prev if not (np.isnan(yoy_last) or np.isnan(yoy_prev)) else np.nan

        rows.append({
            "code_commune": code,
            "base_year": base_year,
            "price_level_log": np.log(level) if level > 0 else np.nan,
            "price_cagr_3y": _cagr(by_year.get(anchor - 3), level, 3),
            "price_cagr_5y": _cagr(by_year.get(anchor - 5), level, 5),
            "liquidity_log": np.log1p(liquidity),
            "volatility": volatility,
            "trend_accel": accel,
        })
    return pd.DataFrame(rows)


def panel_from_prices(price_long: pd.DataFrame, horizon: int = 5, window: int = 5) -> pd.DataFrame:
    """Build the (commune, base_year) training panel from a long price frame.

    Target is the realised forward CAGR from `base_year` to `base_year + horizon`,
    joined on the explicit future year (robust to gaps in a commune's history).
    """
    cols = ["code_commune", "year", "target_cagr", *FEATURE_COLS]
    if price_long.empty:
        return pd.DataFrame(columns=cols)

    p = price_long.sort_values(["code_commune", "year"]).copy()
    p["year"] = p["year"].astype(int)
    fut = p[["code_commune", "year", "median_prix_m2"]].rename(
        columns={"year": "future_year", "median_prix_m2": "future_median"})
    fut["year"] = fut["future_year"] - horizon
    tgt = p.merge(fut[["code_commune", "year", "future_median"]], on=["code_commune", "year"], how="left")
    tgt["target_cagr"] = (tgt["future_median"] / tgt["median_prix_m2"]) ** (1.0 / horizon) - 1.0
    tgt = tgt.dropna(subset=["target_cagr"])
    if tgt.empty:
        return pd.DataFrame(columns=cols)

    feats = pd.concat(
        [features_asof(price_long, int(by), window=window) for by in sorted(tgt["year"].unique())],
        ignore_index=True,
    )
    panel = tgt.merge(feats, left_on=["code_commune", "year"], right_on=["code_commune", "base_year"], how="left")
    return panel.drop(columns=["base_year", "future_median", "future_year"], errors="ignore")


def build_panel(horizon: int = 5, window: int = 5, engine=None) -> pd.DataFrame:
    """One row per (commune, base_year): point-in-time features + forward CAGR."""
    return panel_from_prices(load_price_long(engine), horizon=horizon, window=window)


def x_y(panel: pd.DataFrame):
    cols = [c for c in FEATURE_COLS if c in panel.columns]
    return panel[cols], panel["target_cagr"], cols
