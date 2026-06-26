"""Health establishments (FINESS) -> geolocated ``hospital_points`` layer.

Feeds the per-IRIS hospital-accessibility indicator. FINESS is the national
directory of health and medico-social establishments; this collector reads a
geolocated Opendatasoft mirror and writes points in WGS84.
"""
from __future__ import annotations

import pandas as pd

from rei.ingestion.opendatasoft import OpendatasoftCollector


def _first(df: pd.DataFrame, names: list[str]) -> str | None:
    return next((n for n in names if n in df.columns), None)


def normalize_hospital_points(df: pd.DataFrame) -> pd.DataFrame:
    """Map FINESS records to finess/name/code_commune/lat/lon points.

    Handles either explicit latitude/longitude columns or an Opendatasoft
    ``geo_point_2d`` "lat, lon" string. Rows without coordinates are dropped.
    Pure function, unit-tested offline.
    """
    if df.empty:
        return df
    out = pd.DataFrame()
    fin = _first(df, ["finess", "nofiness", "finess_et", "numero_finess"])
    name = _first(df, ["rs", "raison_sociale", "nom", "rslongue"])
    comm = _first(df, ["code_commune", "com", "depcom", "code_insee", "commune"])
    lat = _first(df, ["latitude", "lat", "coord_lat", "ylat"])
    lon = _first(df, ["longitude", "lon", "lng", "coord_lon", "xlong"])

    out["finess"] = df[fin].astype(str) if fin else [str(i) for i in range(len(df))]
    out["nom"] = df[name] if name else None
    out["code_commune"] = df[comm].astype(str) if comm else None

    if lat is not None and lon is not None:
        out["latitude"] = pd.to_numeric(df[lat], errors="coerce")
        out["longitude"] = pd.to_numeric(df[lon], errors="coerce")
    elif "geo_point_2d" in df.columns:
        gp = df["geo_point_2d"].astype(str).str.split(",", expand=True)
        out["latitude"] = pd.to_numeric(gp[0], errors="coerce")
        out["longitude"] = pd.to_numeric(gp[1], errors="coerce") if gp.shape[1] > 1 else None
    else:
        return pd.DataFrame(columns=["finess", "nom", "code_commune", "latitude", "longitude"])

    return out.dropna(subset=["latitude", "longitude"]).drop_duplicates("finess")


class HospitalsCollector(OpendatasoftCollector):
    source_id = "hospitals_finess"
    base = "https://public.opendatasoft.com/api/explore/v2.1"
    dataset = "finess-etablissements"  # confirm geolocated FINESS slug in catalog

    def collect(self, communes: list[str] | None = None,
                departements: list[str] | None = None, **_) -> int:
        import geopandas as gpd

        from rei.common.store import write_geo

        where = None
        if communes:
            where = "code_commune in (%s)" % ",".join(f'"{c}"' for c in communes)
        elif departements:
            where = "code_departement in (%s)" % ",".join(f'"{d}"' for d in departements)
        df = self.fetch_records(where=where)
        pts = normalize_hospital_points(df)
        if pts.empty:
            return 0
        gdf = gpd.GeoDataFrame(pts, geometry=gpd.points_from_xy(pts["longitude"], pts["latitude"]), crs=4326)
        return write_geo(gdf, "hospital_points", schema="gis", key="finess")
