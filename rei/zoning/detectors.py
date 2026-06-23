"""Commune-level density-change signal blend."""
from __future__ import annotations

import pandas as pd
from sqlalchemy import text

from rei.common.db import get_engine
from rei.zoning.plu_diff import upside_area

WEIGHTS = {"s1": 0.35, "s2": 0.20, "s3": 0.20, "s4": 0.10, "s5": 0.15}


def _permit_acceleration(commune: str) -> float:
    """Ratio of last-12m permits to the prior 12m (capped). >1 = accelerating."""
    sql = text(
        """
        SELECT
          sum(logements_autorises) FILTER (WHERE month >= CURRENT_DATE - INTERVAL '12 months')      AS recent,
          sum(logements_autorises) FILTER (WHERE month <  CURRENT_DATE - INTERVAL '12 months'
                                            AND month >= CURRENT_DATE - INTERVAL '24 months')        AS prior
        FROM core.permits WHERE code_commune = :c
        """
    )
    with get_engine().connect() as conn:
        r = conn.execute(sql, {"c": commune}).fetchone()
    recent, prior = (r[0] or 0), (r[1] or 0)
    if prior <= 0:
        return 1.0 if recent > 0 else 0.0
    return min(recent / prior, 3.0)


def _transport_commitment(commune: str, radius_m: int = 1000) -> int:
    """Count of committed transport-project nodes within radius of the commune."""
    sql = text(
        """
        SELECT count(*) FROM gis.transport_projects tp
        JOIN gis.parcels p ON p.code_commune = :c
        WHERE tp.status IN ('under_construction','commissioning','planned')
          AND ST_DWithin(tp.geometry::geography, ST_Centroid(p.geometry)::geography, :r)
        """
    )
    with get_engine().connect() as conn:
        return int(conn.execute(sql, {"c": commune, "r": radius_m}).scalar() or 0)


def _doc_density_mentions(commune: str) -> int:
    sql = text(
        "SELECT count(*) FROM docs.extraction "
        "WHERE code_commune = :c AND fact_type IN ('density_increase','rezoning')"
    )
    with get_engine().connect() as conn:
        return int(conn.execute(sql, {"c": commune}).scalar() or 0)


def _housing_target_pressure(commune: str) -> int:
    sql = text(
        "SELECT count(*) FROM docs.extraction "
        "WHERE code_commune = :c AND fact_type = 'housing_target'"
    )
    with get_engine().connect() as conn:
        return int(conn.execute(sql, {"c": commune}).scalar() or 0)


def _norm(x: float, cap: float) -> float:
    return max(0.0, min(x / cap, 1.0))


def density_change_score(commune: str) -> dict:
    s1 = _norm(upside_area(commune), 50_000)
    s2 = _norm(_permit_acceleration(commune) - 1.0, 1.0)
    s3 = _norm(_transport_commitment(commune), 2)
    s4 = _norm(_doc_density_mentions(commune), 5)
    s5 = _norm(_housing_target_pressure(commune), 3)
    parts = {"s1": s1, "s2": s2, "s3": s3, "s4": s4, "s5": s5}
    score = 100 * sum(WEIGHTS[k] * v for k, v in parts.items())
    return {"code_commune": commune, "density_change_score": round(score, 1), **parts}


def score_communes(communes: list[str]) -> pd.DataFrame:
    return pd.DataFrame(density_change_score(c) for c in communes)
