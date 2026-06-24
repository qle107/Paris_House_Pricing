"""Geospatial intelligence primitives (blueprint Phase 4).

Pure functions over geometry-derived inputs:
  * gravity_accessibility - capacity-weighted, distance-decayed access to opportunities
    (transit stops, jobs), the principled replacement for the dead raw-count transit term.
  * morans_i - global spatial autocorrelation, used as a diagnostic that a redesigned
    score reflects real market structure rather than being merely monotonic in geography.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def gravity_accessibility(distances_m, capacities=None, d0: float = 800.0) -> float:
    """A = sum_i cap_i * exp(-dist_i / d0).

    `distances_m` are metres to each opportunity; `capacities` weights them (default 1
    each); `d0` is the decay scale (800 m ~ a 10-minute walk). Higher = better connected.
    NaN distances are dropped; an empty set scores 0."""
    d = pd.to_numeric(pd.Series(distances_m), errors="coerce").reset_index(drop=True)
    cap = (pd.Series(1.0, index=d.index) if capacities is None
           else pd.to_numeric(pd.Series(capacities), errors="coerce").reset_index(drop=True)
           .reindex(d.index).fillna(0.0))
    mask = d.notna()
    if not mask.any():
        return 0.0
    return float((cap[mask] * np.exp(-d[mask] / d0)).sum())


def morans_i(values, weights) -> float:
    """Global Moran's I spatial autocorrelation in roughly [-1, 1].

    +1 = strong clustering of similar values, ~0 = random, negative = dispersion.
    `weights` is an n x n spatial weight matrix (contiguity or inverse distance).
    Returns NaN when the weight matrix or the value variance is zero."""
    z = np.asarray(pd.to_numeric(pd.Series(values), errors="coerce"), dtype=float)
    w = np.asarray(weights, dtype=float)
    n = len(z)
    dz = z - z.mean()
    s0 = w.sum()
    denom = float((dz ** 2).sum())
    if s0 == 0 or denom == 0:
        return float("nan")
    num = float(dz.dot(w).dot(dz))
    return (n / s0) * (num / denom)
