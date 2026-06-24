"""Per-IRIS decomposition of the institutional composite score (blueprint Phase 7).

Turns a 0-100 score into the answer an investment committee asks: which factors lifted
it, which held it back, which quality gates fired, and how much the value-trap and
climate haircuts cost. Pure function over the columns ``compute_institutional`` emits -
no I/O, no geopandas - so it is cheap to call per zone and trivial to test.

Contributions are measured against a neutral 50: a positive number means the factor
lifted the score, a negative one means it dragged it down. They sum (plus the 50
baseline) to the pre-gate base, which then has the gates, trap and climate haircut
applied to reach the published ``institutional_score``.
"""
from __future__ import annotations

import math

from rei.scoring.institutional import INSTITUTIONAL_W

# weight key -> the sub-score column compute_institutional emits
COMPONENT_COL = {
    "appreciation": "inst_appreciation", "rental": "inst_rental", "risk": "inst_risk",
    "value_adj": "inst_value_adj", "development": "inst_development", "liquidity": "inst_liquidity",
}

# gate column, human label, predicate on the neutral-filled value - mirrors apply_gates
_GATES = [
    ("inst_appreciation", "appreciation < 40 -> capped at 55", lambda v: v < 40),
    ("inst_rental",       "rental < 40 -> capped at 55",       lambda v: v < 40),
    ("inst_toxicity",     "toxicity > 70 -> x0.85",            lambda v: v > 70),
    ("inst_risk",         "risk < 30 -> x0.85",                lambda v: v < 30),
    ("inst_liquidity",    "liquidity < 15 -> x0.85",           lambda v: v < 15),
]


def _num(row, col, default):
    v = row.get(col)
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return default
    return float(v)


def _raw(row, col):
    """Nullable read: the value, or None when missing/NaN (for display-only fields)."""
    v = row.get(col)
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else float(v)


def decompose(row, weights: dict | None = None) -> dict:
    """Decompose one scored IRIS row (a dict or pandas Series).

    `weights` defaults to the institutional weights; pass ALPHA_W to decompose the
    alpha score. Missing sub-scores are treated as a neutral 50, exactly as the gates do.
    """
    weights = weights or INSTITUTIONAL_W
    contrib = {k: round(weights[k] * (_num(row, COMPONENT_COL[k], 50.0) - 50.0), 1) for k in weights}
    ranked = sorted(contrib.items(), key=lambda kv: kv[1], reverse=True)
    trap = _num(row, "value_trap_score", 0.0)
    climate = _num(row, "climate_multiplier", 1.0)
    return {
        "institutional_score": _raw(row, "institutional_score"),
        "base_pre_gate": round(50.0 + sum(contrib.values()), 1),
        "contributions": dict(ranked),
        "positive_contributors": [kv for kv in ranked if kv[1] > 0],
        "negative_contributors": [kv for kv in ranked if kv[1] < 0][::-1],
        "gates_fired": [msg for col, msg, fired in _GATES if fired(_num(row, col, 50.0))],
        "value_trap_score": trap,
        "trap_haircut_pct": round(0.40 * trap, 1),
        "climate_multiplier": climate,
        "climate_haircut_pct": round((1.0 - climate) * 100, 1),
        "data_coverage": _raw(row, "data_coverage"),
    }
