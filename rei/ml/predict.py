"""Score communes with the trained models -> scores.ml_forecast.

Serving features are built as of the latest transaction year with the same
`features_asof` used in training, so serve-time inputs match train-time inputs.
Output carries the mean estimate, a p10/p90 fair-value band, and the top SHAP
drivers per commune. `name` is looked up purely for display (not a predictor),
so using the current snapshot for it introduces no target leakage.
"""
from __future__ import annotations

import joblib
import pandas as pd

from rei.common.db import get_engine
from rei.common.logging import get_logger
from rei.ml.explain import shap_table
from rei.ml.features import features_asof, load_price_long
from rei.ml.train import MODEL_PATH

log = get_logger(__name__)

_DRIVER_LABELS = {
    "price_level_log": "current price level",
    "price_cagr_3y": "3-year price trend",
    "price_cagr_5y": "5-year price trend",
    "liquidity_log": "sales volume",
    "volatility": "price volatility",
    "trend_accel": "recent momentum",
}


def _friendly_drivers(drivers, eps: float = 0.0005) -> str:
    """Turn [(feature, shap)] into 'sales volume (lowers), current price level (raises)'."""
    parts = []
    for f, v in drivers:
        label = _DRIVER_LABELS.get(f, f)
        direction = "raises" if v > eps else "lowers" if v < -eps else "neutral"
        parts.append(f"{label} ({direction})")
    return ", ".join(parts)


def predict_all(with_shap: bool = True) -> pd.DataFrame:
    bundle = joblib.load(MODEL_PATH)
    mean_model, q_models = bundle["mean_model"], bundle["quantile_models"]
    cols, fill = bundle["features"], bundle["fillna"]

    price_long = load_price_long()
    if price_long.empty:
        raise RuntimeError("No DVF transactions available to build serving features")
    base_year = int(price_long["year"].max())
    feats = features_asof(price_long, base_year, window=bundle.get("window", 5))

    X = feats.reindex(columns=cols)
    for c in cols:
        X[c] = X[c].fillna(fill.get(c))

    out = feats[["code_commune"]].copy()
    out["base_year"] = base_year
    out["horizon"] = bundle.get("horizon")
    out["expected_price_cagr"] = mean_model.predict(X).round(4)
    lo, hi = min(q_models), max(q_models)
    out[f"cagr_p{int(round(lo * 100))}"] = q_models[lo].predict(X).round(4)
    out[f"cagr_p{int(round(hi * 100))}"] = q_models[hi].predict(X).round(4)

    if with_shap:
        drivers = shap_table(mean_model, X)["top_drivers"]
        out["top_drivers"] = drivers.apply(_friendly_drivers)

    out = _with_names(out)
    _write_forecast(out)
    log.info("Wrote %d ML forecasts (base_year=%d)", len(out), base_year)
    front = [c for c in ("code_commune", "name", "base_year", "expected_price_cagr") if c in out]
    return out[front + [c for c in out.columns if c not in front]].sort_values(
        "expected_price_cagr", ascending=False)


def _write_forecast(out: pd.DataFrame) -> None:
    """Persist the forecast where the active backend (and map export) can read it."""
    from rei.common import store
    if store.using_files():
        store.write_table_files(out, "ml_forecast", conflict_cols=["code_commune"])
    else:
        out.to_sql("ml_forecast", get_engine(), schema="scores", if_exists="replace", index=False)


def _with_names(out: pd.DataFrame) -> pd.DataFrame:
    """Best-effort human-readable commune name for display only (not a predictor)."""
    from rei.common import store
    try:
        if store.using_files():
            sc = store.read_table("commune_score")
            if sc is None or sc.empty or "name" not in sc:
                return out
            names = sc[["code_commune", "name"]].drop_duplicates("code_commune")
        else:
            names = pd.read_sql("SELECT code_commune, name FROM scores.mv_commune_features", get_engine())
        names["code_commune"] = names["code_commune"].astype(str)
        return out.merge(names, on="code_commune", how="left")
    except Exception as exc:  # noqa: BLE001 - name is cosmetic
        log.warning("name lookup skipped (%s)", exc)
        return out


if __name__ == "__main__":
    print(predict_all().head(25).to_string(index=False))
