"""Parcel distance to transit, schools, and other point layers."""
from __future__ import annotations

import pandas as pd
from sqlalchemy import text

from rei.common.db import get_engine


def nearest_transit_distance(commune: str) -> pd.DataFrame:
    """Metres from each parcel centroid to the nearest transit stop."""
    sql = text(
        """
        SELECT p.id_parcelle,
               ST_Distance(
                   ST_Centroid(p.geometry)::geography,
                   (SELECT s.geometry::geography
                    FROM gis.transit_stops s
                    ORDER BY p.geometry <-> s.geometry
                    LIMIT 1)
               ) AS dist_transit_m
        FROM gis.parcels p
        WHERE p.code_commune = :c
        """
    )
    with get_engine().connect() as conn:
        return pd.read_sql(sql, conn, params={"c": commune})


def count_within(commune: str, layer: str, radius_m: int = 800) -> pd.DataFrame:
    """Count features of a point layer within `radius_m` of each parcel centroid.

    `layer` is a fully-qualified point table, e.g. 'gis.transit_stops'. 800 m is
    the standard ~10-minute-walk transit catchment used in TOD analysis.
    """
    sql = text(
        f"""
        SELECT p.id_parcelle,
               (SELECT count(*) FROM {layer} f
                WHERE ST_DWithin(ST_Centroid(p.geometry)::geography,
                                 f.geometry::geography, :r)) AS n_within
        FROM gis.parcels p
        WHERE p.code_commune = :c
        """
    )
    with get_engine().connect() as conn:
        return pd.read_sql(sql, conn, params={"c": commune, "r": radius_m})


def school_access(commune: str) -> pd.DataFrame:
    """Mean IPS of schools within 1 km of each parcel (family-segment quality)."""
    sql = text(
        """
        SELECT p.id_parcelle,
               (SELECT avg(sc.ips)
                FROM core.schools sc
                JOIN gis.parcels pp ON pp.code_commune = sc.code_commune
                WHERE sc.code_commune = p.code_commune) AS mean_ips_commune
        FROM gis.parcels p
        WHERE p.code_commune = :c
        """
    )
    with get_engine().connect() as conn:
        return pd.read_sql(sql, conn, params={"c": commune})
