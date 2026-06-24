"""Export file-mode layers to GeoJSON for the static map."""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd

from rei.common import store
from rei.common.logging import get_logger

log = get_logger(__name__)
CRS_METRIC = 2154  # Lambert-93, for metric geometry simplification


def _write(gdf, path: Path):
    if gdf is None or len(gdf) == 0:
        return False
    gdf = gdf.to_crs(4326)
    if path.exists():
        path.unlink()
    gdf.to_file(path, driver="GeoJSON")
    log.info("wrote %s (%d features)", path.name, len(gdf))
    return True


def export_geojson(out_dir: str | Path) -> list[str]:
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    written = []

    communes = store.read_geo("communes")
    if communes is not None and not communes.empty:
        scores = store.read_table("commune_score")
        if not scores.empty:
            communes = communes.merge(scores, on="code_commune", how="left", suffixes=("", "_s"))
            if "attractiveness_score" in communes:
                communes = communes.rename(columns={"attractiveness_score": "score"})
        fc = store.read_table("ml_forecast")
        if fc is not None and not fc.empty:
            keep = [c for c in ["code_commune", "expected_price_cagr", "cagr_p10",
                                "cagr_p90", "top_drivers", "horizon"] if c in fc.columns]
            fc = fc[keep].copy()
            fc["code_commune"] = fc["code_commune"].astype(str)
            communes["code_commune"] = communes["code_commune"].astype(str)
            communes = communes.merge(fc, on="code_commune", how="left")
        if _write(communes, out / "communes.geojson"):
            written.append("communes")

    iris = store.read_geo("iris_scored")
    if iris is not None and not iris.empty:
        fc = store.read_table("ml_forecast")
        if fc is not None and not fc.empty:
            keep = [c for c in ["code_commune", "expected_price_cagr", "cagr_p10",
                                "cagr_p90", "top_drivers", "horizon"] if c in fc.columns]
            fc = fc[keep].copy()
            fc["code_commune"] = fc["code_commune"].astype(str)
            iris["code_commune"] = iris["code_commune"].astype(str)
            iris = iris.merge(fc, on="code_commune", how="left")
        iris = iris.to_crs(CRS_METRIC)
        iris["geometry"] = iris.geometry.simplify(10)
        if _write(iris, out / "iris.geojson"):
            written.append("iris")

    up = store.read_geo("parcel_upside")
    if up is not None and not up.empty:
        up = up.rename(columns={"buildable_upside_m2": "upside_m2"})
        if _write(up, out / "parcels.geojson"):
            written.append("parcels")

    listings = store.read_table("listings")
    if listings is not None and not listings.empty and {"lat", "lon"} <= set(listings.columns):
        pts = gpd.GeoDataFrame(listings.copy(),
                               geometry=gpd.points_from_xy(listings["lon"], listings["lat"]), crs=4326)
        if _write(pts, out / "listings.geojson"):
            written.append("listings")

    for layer, fname in [("zoning", "zoning"), ("transit_stops", "transit"),
                         ("transport_projects", "projects")]:
        if _write(store.read_geo(layer), out / f"{fname}.geojson"):
            written.append(fname)

    return written
