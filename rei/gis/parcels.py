"""Parcel GIS helpers (PostGIS -> GeoPandas, EPSG:2154)."""
from __future__ import annotations

import geopandas as gpd

from rei.common.db import get_engine

CRS_METRIC = 2154  # Lambert-93


def load_parcels(commune: str) -> gpd.GeoDataFrame:
    sql = "SELECT id_parcelle, code_commune, contenance, geometry FROM gis.parcels WHERE code_commune = %(c)s"
    gdf = gpd.read_postgis(sql, get_engine(), geom_col="geometry", params={"c": commune})
    return gdf.to_crs(CRS_METRIC)


def load_buildings(commune: str) -> gpd.GeoDataFrame:
    sql = "SELECT code_commune, geometry FROM gis.buildings WHERE code_commune = %(c)s"
    gdf = gpd.read_postgis(sql, get_engine(), geom_col="geometry", params={"c": commune})
    return gdf.to_crs(CRS_METRIC)


def load_zoning(commune: str, latest_only: bool = True) -> gpd.GeoDataFrame:
    sql = "SELECT code_commune, libelle, typezone, captured_at, geometry FROM gis.zoning WHERE code_commune = %(c)s"
    gdf = gpd.read_postgis(sql, get_engine(), geom_col="geometry", params={"c": commune})
    if latest_only and not gdf.empty and gdf["captured_at"].notna().any():
        gdf = gdf[gdf["captured_at"] == gdf["captured_at"].max()]
    return gdf.to_crs(CRS_METRIC)
