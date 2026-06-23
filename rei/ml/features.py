"""Feature panel for the price-growth ML model."""
from __future__ import annotations

import pandas as pd

from rei.common.db import get_engine

FEATURE_COLS = [
    "pop_cagr", "revenu_median", "permits_per_1000", "loyer_m2",
    "n_risques", "ips_mean", "zoning_share_au", "median_prix_m2_last",
]


def build_panel(horizon: int = 5) -> pd.DataFrame:
    """One row per (commune, base_year): structural features + forward price CAGR."""
    eng = get_engine()
    prices = pd.read_sql(
        """SELECT code_commune, mutation_year AS year,
                  percentile_cont(0.5) WITHIN GROUP (ORDER BY prix_m2) AS median_prix_m2
           FROM core.dvf_transactions
           WHERE prix_m2 BETWEEN 200 AND 25000
           GROUP BY code_commune, mutation_year""",
        eng,
    )
    prices = prices.sort_values(["code_commune", "year"])
    prices["future"] = prices.groupby("code_commune")["median_prix_m2"].shift(-horizon)
    prices["target_cagr"] = (prices["future"] / prices["median_prix_m2"]) ** (1 / horizon) - 1
    panel = prices.dropna(subset=["target_cagr"])

    feats = pd.read_sql("SELECT * FROM scores.mv_commune_features", eng)
    panel = panel.merge(feats[["code_commune"] + [c for c in FEATURE_COLS if c in feats.columns]],
                        on="code_commune", how="left")
    return panel


def x_y(panel: pd.DataFrame):
    cols = [c for c in FEATURE_COLS if c in panel.columns]
    return panel[cols], panel["target_cagr"], cols
