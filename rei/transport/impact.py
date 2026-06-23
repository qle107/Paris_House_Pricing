"""Transport project uplift estimates and ranking."""
from __future__ import annotations

import pandas as pd
from sqlalchemy import text

from rei.common.db import get_engine

# mode -> (primary catchment m, secondary catchment m, peak uplift %, years to peak)
MODE_PROFILE = {
    "metro":  (800, 1500, 0.18, 3),
    "rer":    (1000, 2000, 0.15, 3),
    "train":  (1200, 2500, 0.10, 4),
    "tram":   (500, 1000, 0.10, 2),
    "brt":    (400, 800, 0.06, 2),
    "bus":    (300, 600, 0.03, 1),
}


def expected_uplift(mode: str, dist_m: float, years_to_open: float) -> float:
    """Expected % value uplift for a parcel `dist_m` from a `mode` node.

    Linear distance decay within the secondary catchment; a ramp that is ~40% of
    peak at announcement, reaching peak ~`years_to_peak` after opening.
    """
    prof = MODE_PROFILE.get(mode)
    if not prof:
        return 0.0
    primary, secondary, peak, yrs_peak = prof
    if dist_m > secondary:
        return 0.0
    decay = 1.0 if dist_m <= primary else max(0.0, 1 - (dist_m - primary) / (secondary - primary))
    ramp = max(0.4, min(1.0, 1.0 - years_to_open / (yrs_peak + 6)))
    return peak * decay * ramp


def project_parcel_impact(commune: str, today_year: int) -> pd.DataFrame:
    """For each parcel in a commune, expected uplift from the nearest pipeline node."""
    sql = text(
        """
        WITH nearest AS (
          SELECT p.id_parcelle,
                 tp.mode,
                 EXTRACT(YEAR FROM tp.opening) AS open_year,
                 ST_Distance(ST_Centroid(p.geometry)::geography, tp.geometry::geography) AS dist_m,
                 row_number() OVER (PARTITION BY p.id_parcelle
                                    ORDER BY p.geometry <-> tp.geometry) AS rn
          FROM gis.parcels p
          CROSS JOIN gis.transport_projects tp
          WHERE p.code_commune = :c
        )
        SELECT id_parcelle, mode, open_year, dist_m
        FROM nearest WHERE rn = 1
        """
    )
    with get_engine().connect() as conn:
        df = pd.read_sql(sql, conn, params={"c": commune})
    if df.empty:
        return df
    df["years_to_open"] = (df["open_year"] - today_year).clip(lower=-3)
    df["expected_uplift"] = df.apply(
        lambda r: expected_uplift(r["mode"], r["dist_m"], r["years_to_open"]), axis=1
    )
    return df


def rank_projects() -> pd.DataFrame:
    """Rank pipeline projects by catchment population x uplift x imminence."""
    sql = text(
        """
        SELECT tp.project, tp.line, tp.station, tp.mode, tp.opening,
               (SELECT count(*) FROM gis.parcels p
                WHERE ST_DWithin(p.geometry::geography, tp.geometry::geography, 800)) AS parcels_800m
        FROM gis.transport_projects tp
        """
    )
    with get_engine().connect() as conn:
        df = pd.read_sql(sql, conn)
    if df.empty:
        return df
    df["peak_uplift"] = df["mode"].map(lambda m: MODE_PROFILE.get(m, (0, 0, 0, 0))[2])
    df["score"] = df["parcels_800m"] * df["peak_uplift"]
    return df.sort_values("score", ascending=False)
