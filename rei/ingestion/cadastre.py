"""Cadastre Etalab parcel and building polygons."""
from __future__ import annotations

import geopandas as gpd

from rei.common.db import get_engine
from rei.common.io import cache_path, gunzip
from rei.ingestion.base import Collector

BASE = "https://cadastre.data.gouv.fr/data/etalab-cadastre/latest/geojson/communes"


class CadastreCollector(Collector):
    source_id = "cadastre_parcels"
    rps = 4.0

    def _dep(self, insee: str) -> str:
        return insee[:3] if insee[:2] in ("97", "98") else insee[:2]

    def _download_layer(self, insee: str, layer: str) -> gpd.GeoDataFrame:
        dep = self._dep(insee)
        url = f"{BASE}/{dep}/{insee}/cadastre-{insee}-{layer}.json.gz"
        gz = cache_path(self.source_id, f"{insee}-{layer}.json.gz")
        self.http.stream_to_file(url, gz)
        geojson = gunzip(gz)
        gdf = gpd.read_file(geojson)
        if gdf.crs is None:
            gdf = gdf.set_crs(4326)
        return gdf.to_crs(4326)

    def collect(self, communes: list[str] | None = None, layers: tuple[str, ...] = ("parcelles", "batiments")) -> int:
        if not communes:
            raise ValueError("CadastreCollector requires a `communes` list of INSEE codes")
        from rei.common.store import write_geo
        total = 0
        for insee in communes:
            for layer in layers:
                try:
                    gdf = self._download_layer(insee, layer)
                except Exception:
                    self.log.warning("No cadastre %s for %s", layer, insee)
                    continue
                if gdf.empty:
                    continue
                gdf["code_commune"] = insee
                if layer == "parcelles":
                    table = "parcels"
                    if "id" in gdf.columns:
                        gdf = gdf.rename(columns={"id": "id_parcelle"})
                    cols = [c for c in ["id_parcelle", "code_commune", "section",
                                        "numero", "contenance", "geometry"] if c in gdf.columns]
                else:
                    table = "buildings"
                    cols = [c for c in ["code_commune", "geometry"] if c in gdf.columns]
                write_geo(gdf[cols], table, schema="gis", key="id_parcelle" if table == "parcels" else None)
                total += len(gdf)
                self.log.info("Loaded %d %s for %s", len(gdf), layer, insee)
        return total
