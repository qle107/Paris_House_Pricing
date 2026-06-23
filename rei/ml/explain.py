"""Per-area SHAP attributions for the price-growth model.

Returns the top-k drivers behind each commune's predicted CAGR. SHAP is
optional: if it isn't installed (or fails on the model type), this falls back
to the model's global feature importances so prediction never breaks.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def shap_table(model, X: pd.DataFrame, top_k: int = 3) -> pd.DataFrame:
    """One row per input row, column `top_drivers` = list of (feature, value)."""
    cols = list(X.columns)
    vals = _shap_values(model, X)

    if vals is not None and vals.shape == (len(X), len(cols)):
        drivers = []
        for i in range(len(X)):
            order = np.argsort(np.abs(vals[i]))[::-1][:top_k]
            drivers.append([(cols[j], round(float(vals[i, j]), 4)) for j in order])
    else:  # global-importance fallback (same list for every row)
        imp = getattr(model, "feature_importances_", None)
        glob: list[tuple[str, float]] = []
        if imp is not None:
            order = np.argsort(imp)[::-1][:top_k]
            glob = [(cols[j], round(float(imp[j]), 4)) for j in order]
        drivers = [list(glob) for _ in range(len(X))]

    return pd.DataFrame({"top_drivers": drivers}, index=X.index)


def _shap_values(model, X: pd.DataFrame):
    try:
        import shap
        explainer = shap.TreeExplainer(model)
        vals = np.asarray(explainer.shap_values(X))
        return vals
    except Exception:  # noqa: BLE001 - shap optional / may not support the model
        return None
