"""Score communes with the trained model -> scores.ml_forecast."""
from __future__ import annotations

import joblib
import pandas as pd

from rei.common.db import get_engine
from rei.common.logging import get_logger
from rei.ml.train import MODEL_PATH

log = get_logger(__name__)


def predict_all() -> pd.DataFrame:
    bundle = joblib.load(MODEL_PATH)
    model, cols, fill = bundle["model"], bundle["features"], bundle["fillna"]

    feats = pd.read_sql("SELECT * FROM scores.mv_commune_features", get_engine())
    X = feats.reindex(columns=cols)
    for c in cols:
        X[c] = X[c].fillna(fill.get(c))
    feats["expected_price_cagr"] = model.predict(X)
    out = feats[["code_commune", "name", "expected_price_cagr"]].copy()
    out["expected_price_cagr"] = out["expected_price_cagr"].round(4)
    out.to_sql("ml_forecast", get_engine(), schema="scores", if_exists="replace", index=False)
    log.info("Wrote %d ML forecasts", len(out))
    return out.sort_values("expected_price_cagr", ascending=False)


if __name__ == "__main__":
    print(predict_all().head(25).to_string(index=False))
