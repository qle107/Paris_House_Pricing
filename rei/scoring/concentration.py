"""Economic-concentration risk (blueprint Phase 3.7, Institutional Risk Score).

A local economy dominated by one sector or employer is fragile: a single closure or
sector downturn hits demand, rents and exit liquidity together. The Herfindahl-
Hirschman Index (HHI) of employment-by-sector is the standard measure. These are pure
functions over an employment vector - ready to wire once a per-IRIS SIRENE / INSEE-RP
sector breakdown is ingested (the feed is the only missing piece, same pattern as the
Georisques climate overlay).
"""
from __future__ import annotations

import pandas as pd


def herfindahl(counts) -> float:
    """HHI of a distribution (e.g. jobs per sector): sum of squared shares in [0, 1].
    ~0 = perfectly diversified, 1 = a single sector. NaN for an empty/all-zero input."""
    s = pd.to_numeric(pd.Series(counts), errors="coerce").fillna(0.0)
    total = s.sum()
    if total <= 0:
        return float("nan")
    shares = s / total
    return float((shares ** 2).sum())


def concentration_risk(counts) -> float:
    """0-100 economic-concentration risk from an employment-by-sector vector.

    Uses the size-normalised HHI, HHI* = (HHI - 1/n) / (1 - 1/n), so an evenly spread
    economy scores ~0 whether it has 2 sectors or 20, and a single-sector economy
    scores 100. An empty vector returns a neutral 50 (no data), not a false 0."""
    s = pd.to_numeric(pd.Series(counts), errors="coerce").fillna(0.0)
    s = s[s > 0]
    n = len(s)
    if n == 0:
        return 50.0
    if n == 1:
        return 100.0
    hhi = herfindahl(s)
    hhi_star = (hhi - 1.0 / n) / (1.0 - 1.0 / n)
    return round(max(0.0, min(1.0, hhi_star)) * 100, 1)
