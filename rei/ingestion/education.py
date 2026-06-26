"""Education nationale school directory and IPS."""
from __future__ import annotations

import pandas as pd

from rei.common.db import upsert_dataframe
from rei.ingestion.opendatasoft import OpendatasoftCollector


class EducationCollector(OpendatasoftCollector):
    source_id = "education_ips"
    base = "https://data.education.gouv.fr/api/explore/v2.1"
    dataset = "fr-en-ips-ecoles-ap2022"  # confirm latest millesime slug in catalog

    def collect(self, communes: list[str] | None = None) -> int:
        where = None
        if communes:
            joined = ",".join(f'"{c}"' for c in communes)
            where = f"code_insee in ({joined})"
        df = self.fetch_records(where=where)
        if df.empty:
            return 0
        rename = {"code_insee": "code_commune", "ips": "ips"}
        df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
        keep = [c for c in ["code_commune", "ips", "uai", "nom_etablissement"] if c in df.columns]
        return upsert_dataframe(df[keep].drop_duplicates("uai"), "schools", conflict_cols=("uai",))


def _first(df: pd.DataFrame, names: list[str]) -> str | None:
    return next((n for n in names if n in df.columns), None)


def normalize_school_points(df: pd.DataFrame) -> pd.DataFrame:
    """Map the annuaire-education records to uai/name/code_commune/lat/lon points.

    Heuristic column matching keeps this resilient to ODS millesime renames; rows
    without usable coordinates are dropped. Pure function, unit-tested offline.
    """
    if df.empty:
        return df
    lat = _first(df, ["latitude", "lat", "position.lat", "geolocalisation.lat"])
    lon = _first(df, ["longitude", "lon", "lng", "position.lon", "geolocalisation.lon"])
    uai = _first(df, ["identifiant_de_l_etablissement", "uai", "numero_uai", "code_etablissement"])
    name = _first(df, ["nom_etablissement", "appellation_officielle", "denomination"])
    comm = _first(df, ["code_commune", "code_insee", "code_commune_insee"])
    if lat is None or lon is None:
        return pd.DataFrame(columns=["uai", "nom_etablissement", "code_commune", "latitude", "longitude"])
    out = pd.DataFrame({
        "uai": df[uai].astype(str) if uai else [str(i) for i in range(len(df))],
        "nom_etablissement": df[name] if name else None,
        "code_commune": df[comm].astype(str) if comm else None,
        "latitude": pd.to_numeric(df[lat], errors="coerce"),
        "longitude": pd.to_numeric(df[lon], errors="coerce"),
    })
    return out.dropna(subset=["latitude", "longitude"]).drop_duplicates("uai")


class SchoolLocationsCollector(OpendatasoftCollector):
    """Geolocated school directory (annuaire) -> ``school_points`` geo layer.

    Feeds the per-IRIS school-accessibility indicator (rei.scoring.accessibility_iris),
    which needs coordinates; the IPS collector above stays commune-level.
    """

    source_id = "schools_directory"
    base = "https://data.education.gouv.fr/api/explore/v2.1"
    dataset = "fr-en-annuaire-education"

    def collect(self, communes: list[str] | None = None,
                departements: list[str] | None = None, **_) -> int:
        import geopandas as gpd

        from rei.common.store import write_geo

        frames: list[pd.DataFrame] = []
        if communes:
            joined = ",".join(f'"{c}"' for c in communes)
            frames.append(self.fetch_records(where=f"code_commune in ({joined})"))
        elif departements:
            # One request per department to stay under the ODS 10k offset cap and keep
            # full coverage across Ile-de-France.
            for d in departements:
                frames.append(self.fetch_records(where=f'code_departement="{d}"'))
        else:
            frames.append(self.fetch_records())

        frames = [f for f in frames if f is not None and not f.empty]
        if not frames:
            return 0
        pts = normalize_school_points(pd.concat(frames, ignore_index=True))
        if pts.empty:
            return 0
        gdf = gpd.GeoDataFrame(pts, geometry=gpd.points_from_xy(pts["longitude"], pts["latitude"]), crs=4326)
        return write_geo(gdf, "school_points", schema="gis", key="uai")
