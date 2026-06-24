"""Data-drift detection (blueprint Phase 5).

The Population Stability Index (PSI) compares a new sample of a feature against a
reference distribution. A pipeline that re-scores the whole universe each refresh
should hold and alert when a key input drifts materially, rather than silently
re-ranking on shifted data. Rule of thumb: PSI < 0.1 stable, 0.1-0.25 moderate,
> 0.25 major drift.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def psi(expected, actual, bins: int = 10) -> float:
    """Population Stability Index between a reference (`expected`) and a new (`actual`)
    sample, bucketed on quantiles of the reference. NaN when either side is empty or the
    reference has no spread."""
    e = pd.to_numeric(pd.Series(expected), errors="coerce").dropna()
    a = pd.to_numeric(pd.Series(actual), errors="coerce").dropna()
    if e.empty or a.empty:
        return float("nan")
    edges = np.unique(np.quantile(e, np.linspace(0, 1, bins + 1)))
    if len(edges) < 2:
        return float("nan")
    e_share = np.clip(np.histogram(e, edges)[0] / len(e), 1e-6, None)
    a_share = np.clip(np.histogram(a, edges)[0] / len(a), 1e-6, None)
    return float(np.sum((a_share - e_share) * np.log(a_share / e_share)))
