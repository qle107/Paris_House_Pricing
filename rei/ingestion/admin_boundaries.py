"""Commune boundaries via geo.api.gouv.fr."""
from __future__ import annotations

import geopandas as gpd
from shapely.geometry import MultiPolygon

from rei.common.db import get_engine
from rei.ingestion.base import Collector

API = "https://geo.api.gouv.fr/communes"


class CommunesBoundaryCollector(Collector):
    source_id = "admin_communes"
    rps = 10.0

    def _fetch(self, params: dict) -> gpd.GeoDataFrame:
        params = {**params, "type": "commune-actuelle,arrondissement-municipal",
                  "fields": "nom,code,contour", "format": "geojson", "geometry": "contour"}
        fc = self.http.get_json(API, params=params)
        feats = fc.get("features", []) if isinstance(fc, dict) else []
        if not feats:
            return gpd.GeoDataFrame()
        gdf = gpd.GeoDataFrame.from_features(feats, crs=4326)
        gdf = gdf.rename(columns={"code": "code_commune", "nom": "name"})
        gdf["geometry"] = gdf.geometry.apply(lambda g: g if g and g.geom_type == "MultiPolygon" else MultiPolygon([g]) if g else None)
        return gdf[["code_commune", "name", "geometry"]].dropna(subset=["geometry"])

    def collect(self, communes: list[str] | None = None, departements: list[str] | None = None) -> int:
        frames = []
        if communes:
            for insee in communes:
                frames.append(self._fetch({"code": insee}))
        elif departements:
            for dep in departements:
                frames.append(self._fetch({"codeDepartement": dep}))
        else:
            frames.append(self._fetch({}))  # national
        gdf = gpd.GeoDataFrame(
            __import__("pandas").concat([f for f in frames if not f.empty], ignore_index=True), crs=4326
        ) if any(not f.empty for f in frames) else gpd.GeoDataFrame()
        if gdf.empty:
            return 0
        from rei.common.store import write_geo, using_files
        if not using_files():
            from sqlalchemy import text
            codes = list(gdf["code_commune"].unique())
            with get_engine().begin() as conn:
                conn.execute(text("CREATE SCHEMA IF NOT EXISTS gis"))
                if codes:
                    conn.execute(text("DELETE FROM gis.communes WHERE code_commune = ANY(:c)"), {"c": codes})
        write_geo(gdf, "communes", schema="gis", key="code_commune")
        self.log.info("Loaded %d commune boundaries", len(gdf))
        return len(gdf)
