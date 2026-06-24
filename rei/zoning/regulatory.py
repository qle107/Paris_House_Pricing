"""Regulatory risk from PLU revisions (blueprint Phase 3.7, Institutional Risk Score).

Entitlement uncertainty is a real institutional risk: a PLU revision that downzones an
area cuts its buildable capacity and the development thesis with it. This pairs with
``rei.zoning.plu_diff``, which computes before/after buildable area per zone; this pure
function turns that into a 0-100 risk score.
"""
from __future__ import annotations


def downzoning_risk(buildable_before, buildable_after) -> float:
    """0-100 regulatory risk: the share of buildable capacity lost in a PLU revision.

    0 = unchanged or upzoned (no downside), 100 = fully downzoned. An unknown or zero
    baseline returns a neutral 50 rather than a false 0."""
    b = float(buildable_before) if buildable_before else 0.0
    a = float(buildable_after) if buildable_after is not None else 0.0
    if b <= 0:
        return 50.0
    loss = (b - a) / b
    return round(max(0.0, min(1.0, loss)) * 100, 1)
