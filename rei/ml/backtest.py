"""Walk-forward backtest of the price-growth model.

Expanding window over base years: for each base year t, train on rows with
base_year < t and test on base_year == t. Because features are point-in-time
(see rei.ml.features) this is a genuine out-of-time test with no lookahead, so
it is the check that the leakage fix actually holds.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score

from rei.common.logging import get_logger
from rei.ml.features import build_panel, x_y
from rei.ml.train import _make_mean_model, _make_quantile_model

log = get_logger(__name__)


def walk_forward(horizon: int = 5, window: int = 5, min_train_years: int = 3) -> pd.DataFrame:
    panel = build_panel(horizon, window).dropna(subset=["target_cagr"])
    return walk_forward_panel(panel, min_train_years=min_train_years)


def walk_forward_panel(panel: pd.DataFrame, min_train_years: int = 3) -> pd.DataFrame:
    """One metrics row per fold. Expects a panel from rei.ml.features."""
    folds: list[dict] = []
    for t in sorted(panel["year"].unique()):
        train_df = panel[panel["year"] < t]
        test_df = panel[panel["year"] == t]
        if test_df.empty or train_df["year"].nunique() < min_train_years:
            continue

        Xtr, ytr, _ = x_y(train_df)
        Xte, yte, _ = x_y(test_df)
        fill = Xtr.median(numeric_only=True)
        Xtr_f, Xte_f = Xtr.fillna(fill), Xte.fillna(fill)

        pred = _make_mean_model().fit(Xtr_f, ytr).predict(Xte_f)
        lo = _make_quantile_model(0.1).fit(Xtr_f, ytr).predict(Xte_f)
        hi = _make_quantile_model(0.9).fit(Xtr_f, ytr).predict(Xte_f)
        folds.append({
            "test_year": int(t), "n_train": int(len(Xtr)), "n_test": int(len(Xte)),
            "mae": float(mean_absolute_error(yte, pred)),
            "r2": float(r2_score(yte, pred)) if len(yte) > 1 else float("nan"),
            "coverage_80": float(np.mean((yte >= lo) & (yte <= hi))),
        })

    out = pd.DataFrame(folds)
    if not out.empty:
        log.info("Walk-forward: %d folds | mean MAE=%.4f | mean 80%% coverage=%.2f",
                 len(out), out["mae"].mean(), out["coverage_80"].mean())
    return out


if __name__ == "__main__":
    print(walk_forward().to_string(index=False))
