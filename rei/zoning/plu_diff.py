"""Diff PLU/PLUi zoning snapshots for reclassifications."""
from __future__ import annotations

import geopandas as gpd
import pandas as pd

from rei.common.db import get_engine
from rei.gis.density import _zone_family

CRS_METRIC = 2154

UPSIDE_TRANSITIONS = {
    ("N", "AU"): "natural_to_urbanisable",
    ("A", "AU"): "agri_to_urbanisable",
    ("AU", "U"): "urbanisable_to_urban",
    ("N", "U"): "natural_to_urban",
    ("A", "U"): "agri_to_urban",
}


def _snapshot(commune: str, captured_at) -> gpd.GeoDataFrame:
    sql = """
        SELECT typezone, geometry FROM gis.zoning
        WHERE code_commune = %(c)s AND captured_at = %(t)s
    """
    gdf = gpd.read_postgis(sql, get_engine(), geom_col="geometry", params={"c": commune, "t": captured_at})
    gdf["fam"] = gdf["typezone"].map(_zone_family)
    return gdf.to_crs(CRS_METRIC)


def list_snapshots(commune: str) -> list:
    sql = "SELECT DISTINCT captured_at FROM gis.zoning WHERE code_commune = %(c)s ORDER BY captured_at"
    return pd.read_sql(sql, get_engine(), params={"c": commune})["captured_at"].tolist()


def diff_latest_two(commune: str) -> pd.DataFrame:
    """Return reclassified areas between the two most recent snapshots."""
    snaps = list_snapshots(commune)
    if len(snaps) < 2:
        return pd.DataFrame(columns=["transition", "label", "area_m2"])
    old, new = _snapshot(commune, snaps[-2]), _snapshot(commune, snaps[-1])
    overlay = gpd.overlay(old[["fam", "geometry"]], new[["fam", "geometry"]], how="intersection")
    overlay = overlay.rename(columns={"fam_1": "fam_old", "fam_2": "fam_new"})
    changed = overlay[overlay["fam_old"] != overlay["fam_new"]].copy()
    if changed.empty:
        return pd.DataFrame(columns=["transition", "label", "area_m2"])
    changed["area_m2"] = changed.geometry.area
    changed["transition"] = list(zip(changed["fam_old"], changed["fam_new"]))
    changed["label"] = changed["transition"].map(UPSIDE_TRANSITIONS).fillna("other")
    return (
        changed.groupby(["transition", "label"], as_index=False)["area_m2"].sum()
        .sort_values("area_m2", ascending=False)
    )


def upside_area(commune: str) -> float:
    """Total m2 reclassified into a higher-density family in the latest diff."""
    d = diff_latest_two(commune)
    return float(d.loc[d["label"] != "other", "area_m2"].sum()) if not d.empty else 0.0
