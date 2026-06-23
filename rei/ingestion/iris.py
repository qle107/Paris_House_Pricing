"""IRIS contours from OpenDataSoft georef-france-iris."""
from __future__ import annotations

import geopandas as gpd
from shapely.geometry import shape

from rei.ingestion.base import Collector

ODS = ("https://public.opendatasoft.com/api/explore/v2.1/catalog/datasets/"
       "georef-france-iris/records")
PAGE = 100  # ODS Explore v2.1 caps records at 100/request


def _first(v):
    return v[0] if isinstance(v, list) and v else (None if isinstance(v, list) else v)


class IrisContoursCollector(Collector):
    source_id = "iris_contours"
    rps = 4.0

    def _fetch_where(self, where: str, feats: list[dict]) -> None:
        offset = 0
        while True:
            payload = self.http.get_json(ODS, params={
                "where": where,
                "select": "iris_code,iris_name,com_code,com_arm_code,geo_shape",
                "limit": PAGE, "offset": offset,
            })
            rows = payload.get("results", [])
            for r in rows:
                geom = (r.get("geo_shape") or {}).get("geometry")
                if not geom:
                    continue
                feats.append({
                    "iris_code": _first(r.get("iris_code")),
                    "iris_name": _first(r.get("iris_name")),
                    "code_commune": _first(r.get("com_arm_code")) or _first(r.get("com_code")),
                    "geometry": shape(geom),
                })
            offset += len(rows)
            if len(rows) < PAGE or offset >= payload.get("total_count", 0):
                break

    def collect(self, communes: list[str] | None = None,
                departements: list[str] | None = None) -> int:
        feats: list[dict] = []
        if departements:
            for dep in departements:
                self._fetch_where(f'dep_code="{dep}"', feats)
                self.log.info("Loaded %d IRIS so far (through dept %s)", len(feats), dep)
        else:
            for code in communes or []:
                self._fetch_where(f'com_code="{code}" or com_arm_code="{code}"', feats)
                self.log.info("Loaded %d IRIS so far (through %s)", len(feats), code)
        if not feats:
            return 0
        gdf = gpd.GeoDataFrame(feats, geometry="geometry", crs=4326).drop_duplicates("iris_code")
        from rei.common.store import write_geo
        write_geo(gdf, "iris", schema="gis", key="iris_code")
        return len(gdf)
