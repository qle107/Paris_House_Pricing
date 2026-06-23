"""Train forward price-growth models.

Two heads are trained on the same point-in-time features:
  * a mean point estimate (expected forward price CAGR), and
  * p10 / p50 / p90 quantile models that give a fair-value band.

Validation is the last base year held out (a forward split). Use
`rei.ml.backtest.walk_forward` for the full expanding-window backtest.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import joblib
from sklearn.metrics import mean_absolute_error, r2_score

from config.settings import settings
from rei.common.logging import get_logger
from rei.ml.features import build_panel, x_y

log = get_logger(__name__)
MODEL_PATH = settings.data_dir / "models" / "price_growth.joblib"
QUANTILES = (0.1, 0.5, 0.9)


def train(horizon: int = 5, window: int = 5) -> dict:
    panel = build_panel(horizon, window).dropna(subset=["target_cagr"])
    if panel.empty:
        raise RuntimeError("Empty training panel - load DVF transactions first")

    val_year = int(panel["year"].max())
    train_df = panel[panel["year"] < val_year]
    val_df = panel[panel["year"] == val_year]
    if train_df.empty:
        train_df = val_df = panel  # tiny-data fallback

    Xtr, ytr, cols = x_y(train_df)
    Xva, yva, _ = x_y(val_df)
    fill = Xtr.median(numeric_only=True)
    Xtr_f, Xva_f = Xtr.fillna(fill), Xva.fillna(fill)

    mean_model = _make_mean_model().fit(Xtr_f, ytr)
    q_models = {q: _make_quantile_model(q).fit(Xtr_f, ytr) for q in QUANTILES}

    pred = mean_model.predict(Xva_f)
    band = {q: q_models[q].predict(Xva_f) for q in QUANTILES}
    metrics = {
        "mae": float(mean_absolute_error(yva, pred)),
        "r2": float(r2_score(yva, pred)) if len(yva) > 1 else float("nan"),
        "pinball_p50": float(_pinball(yva, band[0.5], 0.5)),
        "interval_coverage_80": float(np.mean((yva >= band[0.1]) & (yva <= band[0.9]))),
        "n_train": int(len(Xtr)), "n_val": int(len(Xva)), "val_year": val_year,
    }
    log.info("Model metrics: %s", metrics)

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({
        "mean_model": mean_model, "quantile_models": q_models, "quantiles": QUANTILES,
        "features": cols, "fillna": fill.to_dict(), "metrics": metrics,
        "importance": _global_importance(mean_model, cols),
        "horizon": horizon, "window": window,
    }, MODEL_PATH)
    return metrics


def _make_mean_model():
    try:
        from lightgbm import LGBMRegressor
        return LGBMRegressor(n_estimators=600, learning_rate=0.03, num_leaves=31,
                             subsample=0.8, colsample_bytree=0.8, random_state=42)
    except Exception:  # noqa: BLE001 - LightGBM optional; sklearn is always present
        from sklearn.ensemble import GradientBoostingRegressor
        return GradientBoostingRegressor(random_state=42)


def _make_quantile_model(alpha: float):
    try:
        from lightgbm import LGBMRegressor
        return LGBMRegressor(objective="quantile", alpha=alpha, n_estimators=600,
                             learning_rate=0.03, num_leaves=31, subsample=0.8,
                             colsample_bytree=0.8, random_state=42)
    except Exception:  # noqa: BLE001
        from sklearn.ensemble import GradientBoostingRegressor
        return GradientBoostingRegressor(loss="quantile", alpha=alpha, random_state=42)


def _pinball(y, pred, q: float) -> float:
    """Pinball (quantile) loss; equals 0.5*MAE at q=0.5."""
    y, pred = np.asarray(y, float), np.asarray(pred, float)
    d = y - pred
    return float(np.mean(np.maximum(q * d, (q - 1) * d)))


def _global_importance(model, cols) -> dict:
    imp = getattr(model, "feature_importances_", None)
    if imp is None:
        return {}
    return {c: float(v) for c, v in sorted(zip(cols, imp), key=lambda kv: kv[1], reverse=True)}


if __name__ == "__main__":
    print(train())
