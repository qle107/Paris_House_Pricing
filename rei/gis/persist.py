"""Persist parcel buildable-upside to scores.parcel_upside."""
from __future__ import annotations

import geopandas as gpd
from sqlalchemy import text

from rei.common.db import get_engine
from rei.common.logging import get_logger
from rei.gis.density import buildable_upside

log = get_logger(__name__)


def compute_and_store_upside(commune: str) -> int:
    gdf = buildable_upside(commune)  # in EPSG:2154
    if gdf is None or gdf.empty:
        log.warning("No parcels/zoning to compute upside for %s", commune)
        return 0
    keep = [c for c in ["id_parcelle", "code_commune", "parcel_area", "far_existing",
                        "zone_family", "buildable_upside_m2", "geometry"] if c in gdf.columns]
    out = gdf[keep].copy().to_crs(4326)
    out["expected_uplift"] = None  # join rei.transport.impact here when projects are loaded

    from rei.common.store import write_geo, using_files
    if not using_files():
        codes = list(out["id_parcelle"].dropna().unique())
        if codes:
            with get_engine().begin() as conn:
                conn.execute(text("DELETE FROM scores.parcel_upside WHERE id_parcelle = ANY(:c)"), {"c": codes})
    write_geo(out, "parcel_upside", schema="scores", key="id_parcelle")
    log.info("Stored upside for %d parcels in %s", len(out), commune)
    return len(out)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Compute + store parcel buildable-upside for the map")
    ap.add_argument("--communes", required=True, help="comma-separated INSEE codes")
    args = ap.parse_args()
    total = sum(compute_and_store_upside(c) for c in args.communes.split(","))
    print(f"stored upside for {total} parcels")
