"""Per-IRIS forward-looking development score from the project pipeline.

Aggregates the transport (``rei.transport.projects``) and development
(``rei.development.projects``) seeds into one 0-100 ``future_development_score``
per IRIS: the strongest distance-decayed catalyst nearby, plus a mild
agglomeration bonus for additional projects in catchment. Pure GeoPandas, so it
runs in file-storage mode without a database.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from rei.common.logging import get_logger
from rei.transport.impact import MODE_PROFILE

log = get_logger(__name__)

CRS_METRIC = 2154          # Lambert-93, metric
DEV_CATCHMENT_M = 1500     # flat catchment for development projects
AGGLO_WEIGHT = 0.15        # weight on secondary catalysts beyond the strongest


def _projects_metric(transport, dev):
    """Unify transport + development seeds into one metric-CRS point frame."""
    import geopandas as gpd

    t = transport.copy()
    t["name"] = t["station"]
    t["catchment_m"] = t["mode"].map(lambda m: MODE_PROFILE.get(m, (0, 1500, 0, 0))[1])
    t["kind"] = "transport"

    d = dev.copy()
    d["name"] = d["project"]
    d["catchment_m"] = DEV_CATCHMENT_M
    d["kind"] = "development"

    cols = ["name", "kind", "impact_score", "catchment_m", "geometry"]
    p = gpd.GeoDataFrame(pd.concat([t[cols], d[cols]], ignore_index=True), crs=transport.crs)
    return p.to_crs(CRS_METRIC)


def future_development_scores(zones, transport, dev, id_col: str = "iris_code") -> pd.DataFrame:
    """Score every zone by nearby planned transport + development projects.

    ``zones`` is a polygon GeoDataFrame (e.g. IRIS contours) with ``id_col``.
    Returns one row per zone with ``future_development_score`` (0-100),
    ``fdev_n_projects`` in catchment, and the top catalyst's name/score.
    """
    import geopandas as gpd

    p = _projects_metric(transport, dev)
    px, py = p.geometry.x.to_numpy(), p.geometry.y.to_numpy()

    z = zones[[id_col, "geometry"]].to_crs(CRS_METRIC).copy()
    cent = z.geometry.centroid
    zc = gpd.GeoDataFrame({id_col: z[id_col].to_numpy()}, geometry=cent, crs=CRS_METRIC)

    # Match zone centroids to project catchment circles, then decay by true distance.
    circles = p.copy()
    circles["geometry"] = p.geometry.buffer(p["catchment_m"].to_numpy())
    circles["pidx"] = np.arange(len(circles))
    pairs = gpd.sjoin(zc, circles[["pidx", "geometry"]], predicate="within", how="inner")
    if pairs.empty:
        out = pd.DataFrame({id_col: zones[id_col]})
        out["future_development_score"] = 0.0
        out["fdev_n_projects"] = 0
        out["fdev_top_project"] = None
        out["fdev_top_score"] = 0.0
        return out

    pidx = pairs["pidx"].to_numpy()
    zx = pairs.geometry.x.to_numpy()
    zy = pairs.geometry.y.to_numpy()
    dist = np.hypot(zx - px[pidx], zy - py[pidx])
    catch = circles["catchment_m"].to_numpy()[pidx]
    decay = np.clip(1.0 - dist / catch, 0.0, 1.0)
    contrib = p["impact_score"].to_numpy()[pidx] * decay

    df = pd.DataFrame({
        id_col: pairs[id_col].to_numpy(),
        "name": p["name"].to_numpy()[pidx],
        "contrib": contrib,
    })

    # Strongest catalyst (primary) + a mild agglomeration bonus on the rest.
    grp = df.groupby(id_col, sort=False)["contrib"]
    stats = grp.agg(primary="max", total="sum", fdev_n_projects="count")
    stats["fdev_top_project"] = df.loc[grp.idxmax().to_numpy(), "name"].to_numpy()
    stats["future_development_score"] = (
        (stats["primary"] + AGGLO_WEIGHT * (stats["total"] - stats["primary"]))
        .clip(upper=100.0).round(1)
    )
    stats["fdev_top_score"] = stats["primary"].round(1)
    stats = stats.reset_index()

    cols = [id_col, "future_development_score", "fdev_n_projects", "fdev_top_project", "fdev_top_score"]
    out = pd.DataFrame({id_col: zones[id_col]}).merge(stats[cols], on=id_col, how="left")
    out["future_development_score"] = out["future_development_score"].fillna(0.0)
    out["fdev_n_projects"] = out["fdev_n_projects"].fillna(0).astype(int)
    out["fdev_top_score"] = out["fdev_top_score"].fillna(0.0)
    return out


def run_files() -> int:
    """File-mode entry point: read IRIS contours + seeds, write data/tables/future_development."""
    from rei.common.store import read_geo, write_table_files
    from rei.development.projects import seed_frame as dev_seed
    from rei.transport.projects import seed_frame as transport_seed

    zones = read_geo("iris")
    if zones is None or zones.empty:
        log.warning("No IRIS contours in store; run iris_contours ingestion first.")
        return 0
    scores = future_development_scores(zones, transport_seed(), dev_seed())
    return write_table_files(scores, "future_development", conflict_cols=("iris_code",))
