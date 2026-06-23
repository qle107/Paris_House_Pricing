"""Scoring normalisation helpers (percentile rank, thresholds)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def percentile_score(series: pd.Series, direction: int = 1) -> pd.Series:
    """Map values to 0-100 by percentile rank; NaNs -> 50."""
    s = pd.to_numeric(series, errors="coerce")
    ranks = s.rank(pct=True, ascending=(direction > 0))
    out = (ranks * 100).round(1)
    return out.fillna(50.0)


def threshold_score(value: float, bands: list[tuple[float, float]]) -> float:
    """Piecewise map: bands = [(upper_bound, score), ...] ascending by bound."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return 50.0
    for upper, score in bands:
        if value <= upper:
            return float(score)
    return float(bands[-1][1])


def risk_multiplier(n_risques: float, full_at: int, min_mult: float) -> float:
    if n_risques is None or (isinstance(n_risques, float) and np.isnan(n_risques)):
        return 1.0
    frac = min(n_risques / full_at, 1.0)
    return 1.0 - frac * (1.0 - min_mult)
