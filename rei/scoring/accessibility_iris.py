"""Per-IRIS accessibility to public amenities (schools, hospitals) in file mode.

Mirrors ``future_development.py``: pure GeoPandas, so it runs in file-storage mode
without a database. For each IRIS, an amenity within a walk/drive catchment of the
zone centroid contributes ``1 - dist/catchment`` (distance-decayed), the
contributions are summed into a raw access index, and the index is percentile-
normalised to 0-100 across zones. A missing point layer yields a NaN score so the
liveability composite drops it and renormalises rather than scoring a fake 50.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from rei.common.logging import get_logger
from rei.scoring.indicators import percentile_score

log = get_logger(__name__)

CRS_METRIC = 2154           # Lambert-93, metric
SCHOOL_CATCHMENT_M = 1000   # ~12-min walk to a school
HOSPITAL_CATCHMENT_M = 3000  # wider catchment for hospitals / clinics


def _amenity_access(zones, points, catchment_m: float, id_col: str = "iris_code") -> pd.DataFrame:
    """Distance-decayed amenity count per zone centroid.

    Returns one row per ``zones[id_col]`` with ``raw`` (sum of decays, NaN only when
    the whole point layer is absent) and ``n_within`` (amenities in catchment).
    """
    import geopandas as gpd

    base = pd.DataFrame({id_col: zones[id_col].astype(str).to_numpy()})
    if points is None or len(points) == 0:
        base["raw"] = np.nan
        base["n_within"] = 0
        return base

    z = zones[[id_col, "geometry"]].to_crs(CRS_METRIC)
    zc = gpd.GeoDataFrame({id_col: z[id_col].astype(str).to_numpy()},
                          geometry=z.geometry.centroid, crs=CRS_METRIC)
    p = points.to_crs(CRS_METRIC).reset_index(drop=True)
    px, py = p.geometry.x.to_numpy(), p.geometry.y.to_numpy()

    circles = gpd.GeoDataFrame({"pidx": np.arange(len(p))},
                               geometry=p.geometry.buffer(catchment_m), crs=CRS_METRIC)
    pairs = gpd.sjoin(zc, circles, predicate="within", how="inner")
    if pairs.empty:
        base["raw"] = 0.0
        base["n_within"] = 0
        return base

    pidx = pairs["pidx"].to_numpy()
    dist = np.hypot(pairs.geometry.x.to_numpy() - px[pidx],
                    pairs.geometry.y.to_numpy() - py[pidx])
    decay = np.clip(1.0 - dist / catchment_m, 0.0, 1.0)
    agg = (pd.DataFrame({id_col: pairs[id_col].to_numpy(), "decay": decay})
           .groupby(id_col).agg(raw=("decay", "sum"), n_within=("decay", "size")).reset_index())
    out = base.merge(agg, on=id_col, how="left")
    out["raw"] = out["raw"].fillna(0.0)
    out["n_within"] = out["n_within"].fillna(0).astype(int)
    return out


def accessibility_scores(zones, schools, hospitals, id_col: str = "iris_code") -> pd.DataFrame:
    """0-100 school and hospital access per zone, plus raw counts in catchment."""
    out = pd.DataFrame({id_col: zones[id_col].astype(str).to_numpy()})
    sa = _amenity_access(zones, schools, SCHOOL_CATCHMENT_M, id_col)
    ha = _amenity_access(zones, hospitals, HOSPITAL_CATCHMENT_M, id_col)
    out = out.merge(sa.rename(columns={"raw": "_s_raw", "n_within": "n_schools_1km"}), on=id_col, how="left")
    out = out.merge(ha.rename(columns={"raw": "_h_raw", "n_within": "n_hospitals_3km"}), on=id_col, how="left")

    out["school_access_score"] = (percentile_score(out["_s_raw"], 1)
                                  if out["_s_raw"].notna().any() else np.nan)
    out["hospital_access_score"] = (percentile_score(out["_h_raw"], 1)
                                    if out["_h_raw"].notna().any() else np.nan)
    return out.drop(columns=["_s_raw", "_h_raw"])


def run_files() -> int:
    """File-mode entry point: read IRIS contours + point layers, write data/tables/accessibility."""
    from rei.common.store import read_geo, write_table_files

    zones = read_geo("iris")
    if zones is None or zones.empty:
        log.warning("No IRIS contours in store; run iris_contours ingestion first.")
        return 0
    schools = read_geo("school_points")
    hospitals = read_geo("hospital_points")
    if (schools is None or schools.empty) and (hospitals is None or hospitals.empty):
        log.warning("No school_points/hospital_points layers; run schools_directory / "
                    "hospitals_finess ingestion first.")
    scores = accessibility_scores(zones, schools, hospitals)
    return write_table_files(scores, "accessibility", conflict_cols=("iris_code",))
