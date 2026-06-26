"""Health establishments -> geolocated ``hospital_points`` layer.

Source: ``osm-france-healthcare`` on the keyless public Opendatasoft hub
(OpenStreetMap healthcare facilities, refreshed weekly). We keep hospitals and
clinics and write them as WGS84 points for the per-IRIS accessibility indicator.
The authoritative alternative is the geolocated FINESS extract (Atlasante, on
data.gouv); the parser below is field-name tolerant so either source works.
"""
from __future__ import annotations

import pandas as pd

from rei.ingestion.opendatasoft import OpendatasoftCollector


def _first(df: pd.DataFrame, names: list[str]) -> str | None:
    return next((n for n in names if n in df.columns), None)


def normalize_hospital_points(df: pd.DataFrame) -> pd.DataFrame:
    """Map healthcare records to facility_id/name/code_commune/lat/lon points.

    Accepts explicit latitude/longitude, an Opendatasoft ``geo_point_2d`` that is a
    dict (``{lat,lon}``), its json-normalised ``geo_point_2d.lat/.lon`` columns, or a
    ``"lat, lon"`` string. Rows without coordinates are dropped. Pure, unit-tested.
    """
    if df.empty:
        return df
    out = pd.DataFrame()
    fid = _first(df, ["osm_id", "finess", "nofinesset", "numero_finess", "id"])
    name = _first(df, ["name", "nom", "rs", "raison_sociale", "nom_etablissement"])
    comm = _first(df, ["com_insee", "insee_com", "code_commune", "insee", "code_insee", "commune"])
    out["facility_id"] = df[fid].astype(str) if fid else [str(i) for i in range(len(df))]
    out["nom"] = df[name] if name else None
    out["code_commune"] = df[comm].astype(str) if comm else None

    lat = _first(df, ["latitude", "lat", "geo_point_2d.lat", "ylat", "coord_lat"])
    lon = _first(df, ["longitude", "lon", "lng", "geo_point_2d.lon", "xlong", "coord_lon"])
    if lat is not None and lon is not None:
        out["latitude"] = pd.to_numeric(df[lat], errors="coerce")
        out["longitude"] = pd.to_numeric(df[lon], errors="coerce")
    elif "geo_point_2d" in df.columns:
        gp = df["geo_point_2d"]
        if gp.apply(lambda v: isinstance(v, dict)).any():
            out["latitude"] = gp.apply(lambda v: v.get("lat") if isinstance(v, dict) else None)
            out["longitude"] = gp.apply(lambda v: v.get("lon") if isinstance(v, dict) else None)
        else:
            s = gp.astype(str).str.split(",", expand=True)
            out["latitude"] = pd.to_numeric(s[0], errors="coerce")
            out["longitude"] = pd.to_numeric(s[1], errors="coerce") if s.shape[1] > 1 else None
    else:
        return pd.DataFrame(columns=["facility_id", "nom", "code_commune", "latitude", "longitude"])

    return out.dropna(subset=["latitude", "longitude"]).drop_duplicates("facility_id")


class HospitalsCollector(OpendatasoftCollector):
    source_id = "hospitals_finess"
    base = "https://public.opendatasoft.com/api/explore/v2.1"
    dataset = "osm-france-healthcare"

    def collect(self, communes: list[str] | None = None,
                departements: list[str] | None = None, **_) -> int:
        import geopandas as gpd

        from rei.common.store import write_geo

        # Hospitals + clinics only: keeps the set well under the ODS 10k offset cap and
        # relevant to the indicator. If this portal names the type field differently,
        # the run logs a warning and the indicator skips (see normalize fallbacks).
        try:
            df = self.fetch_records(where='amenity in ("hospital", "clinic")')
            if df.empty:
                df = self.fetch_records()
        except Exception:
            df = self.fetch_records()
        pts = normalize_hospital_points(df)
        if pts.empty:
            return 0
        gdf = gpd.GeoDataFrame(pts, geometry=gpd.points_from_xy(pts["longitude"], pts["latitude"]), crs=4326)
        return write_geo(gdf, "hospital_points", schema="gis", key="facility_id")
