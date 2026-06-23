"""Parcel density metrics: footprint, CES, estimated FAR, buildable upside."""
from __future__ import annotations

import geopandas as gpd
import pandas as pd

from rei.gis.parcels import load_buildings, load_parcels, load_zoning

# Default max FAR by zone family when PLU has no numeric COS.
DEFAULT_MAX_FAR = {"U": 2.0, "AU": 1.5, "A": 0.0, "N": 0.05}


def _zone_family(typezone: str | None) -> str:
    if not typezone:
        return "U"
    t = typezone.upper()
    for fam in ("AU", "U", "A", "N"):
        if t.startswith(fam):
            return fam
    return "U"


def parcel_density(commune: str, default_storeys: float = 2.0) -> gpd.GeoDataFrame:
    """Compute footprint, CES and estimated FAR per parcel."""
    parcels = load_parcels(commune)
    buildings = load_buildings(commune)
    if parcels.empty:
        return parcels
    parcels["parcel_area"] = parcels.geometry.area

    if buildings.empty:
        parcels["footprint"] = 0.0
    else:
        joined = gpd.overlay(buildings[["geometry"]], parcels[["id_parcelle", "geometry"]], how="intersection")
        joined["footprint"] = joined.geometry.area
        fp = joined.groupby("id_parcelle")["footprint"].sum()
        parcels = parcels.merge(fp.rename("footprint"), on="id_parcelle", how="left")
        parcels["footprint"] = parcels["footprint"].fillna(0.0)

    parcels["ces"] = parcels["footprint"] / parcels["parcel_area"].replace(0, pd.NA)
    parcels["est_floor_area"] = parcels["footprint"] * default_storeys
    parcels["far_existing"] = parcels["est_floor_area"] / parcels["parcel_area"].replace(0, pd.NA)
    return parcels


def buildable_upside(commune: str) -> gpd.GeoDataFrame:
    """Attach dominant zoning + estimate extra buildable floor area per parcel."""
    parcels = parcel_density(commune)
    zoning = load_zoning(commune)
    if parcels.empty or zoning.empty:
        parcels["zone_family"] = None
        parcels["buildable_upside_m2"] = pd.NA
        return parcels

    inter = gpd.overlay(parcels[["id_parcelle", "geometry"]], zoning[["typezone", "geometry"]], how="intersection")
    inter["a"] = inter.geometry.area
    dom = inter.sort_values("a").drop_duplicates("id_parcelle", keep="last")[["id_parcelle", "typezone"]]
    parcels = parcels.merge(dom, on="id_parcelle", how="left")

    parcels["zone_family"] = parcels["typezone"].map(_zone_family)
    parcels["max_far"] = parcels["zone_family"].map(DEFAULT_MAX_FAR).fillna(1.0)
    parcels["buildable_upside_m2"] = (
        (parcels["max_far"] - parcels["far_existing"].fillna(0)).clip(lower=0)
        * parcels["parcel_area"]
    )
    return parcels
