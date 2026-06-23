"""Train forward price-growth model (LightGBM, XGBoost fallback)."""
from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import mean_absolute_error, r2_score

from config.settings import settings
from rei.common.logging import get_logger
from rei.ml.features import build_panel, x_y

log = get_logger(__name__)
MODEL_PATH = settings.data_dir / "models" / "price_growth.joblib"


def train(horizon: int = 5):
    panel = build_panel(horizon).dropna(subset=["target_cagr"])
    if panel.empty:
        raise RuntimeError("Empty training panel - load DVF + features first")

    val_year = panel["year"].max()
    train_df = panel[panel["year"] < val_year]
    val_df = panel[panel["year"] == val_year]
    if train_df.empty:
        train_df, val_df = panel, panel  # tiny-data fallback

    Xtr, ytr, cols = x_y(train_df)
    Xva, yva, _ = x_y(val_df)

    model = _make_model()
    model.fit(Xtr.fillna(Xtr.median()), ytr)
    pred = model.predict(Xva.fillna(Xtr.median()))
    metrics = {"mae": float(mean_absolute_error(yva, pred)),
               "r2": float(r2_score(yva, pred)) if len(yva) > 1 else float("nan"),
               "n_train": int(len(Xtr)), "n_val": int(len(Xva))}
    log.info("Model metrics: %s", metrics)

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "features": cols, "metrics": metrics,
                 "fillna": Xtr.median().to_dict()}, MODEL_PATH)
    return metrics


def _make_model():
    try:
        from lightgbm import LGBMRegressor
        return LGBMRegressor(n_estimators=600, learning_rate=0.03, num_leaves=31,
                             subsample=0.8, colsample_bytree=0.8, random_state=42)
    except Exception:
        from xgboost import XGBRegressor
        return XGBRegressor(n_estimators=600, learning_rate=0.03, max_depth=5,
                            subsample=0.8, colsample_bytree=0.8, random_state=42)


if __name__ == "__main__":
    print(train())
