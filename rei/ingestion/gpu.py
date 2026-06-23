"""PLU/PLUi zoning via API Carto GPU."""
from __future__ import annotations

import datetime as dt
import json

import geopandas as gpd
import pandas as pd

from rei.common.db import get_engine
from rei.ingestion.base import Collector

APICARTO = "https://apicarto.ign.fr/api"


class GpuCollector(Collector):
    source_id = "gpu_zoning"
    rps = 2.0
    endpoint = "zone-urba"
    target_table = "zoning"

    def commune_geometry(self, insee: str) -> dict:
        fc = self.http.get_json(f"{APICARTO}/cadastre/commune", params={"code_insee": insee})
        feats = fc.get("features", [])
        if not feats:
            raise RuntimeError(f"No commune geometry for {insee}")
        return feats[0]["geometry"]

    def fetch(self, geom: dict, limit: int = 1000) -> gpd.GeoDataFrame:
        features: list[dict] = []
        start = 0
        while True:
            fc = self.http.get_json(
                f"{APICARTO}/gpu/{self.endpoint}",
                params={"geom": json.dumps(geom), "_limit": limit, "_start": start},
            )
            batch = fc.get("features", [])
            features.extend(batch)
            if len(batch) < limit:
                break
            start += limit
        if not features:
            return gpd.GeoDataFrame()
        gdf = gpd.GeoDataFrame.from_features(features, crs=4326)
        gdf["captured_at"] = dt.datetime.utcnow()
        return gdf

    def collect(self, communes: list[str] | None = None) -> int:
        if not communes:
            raise ValueError("GpuCollector requires a `communes` list of INSEE codes")
        total = 0
        for insee in communes:
            try:
                geom = self.commune_geometry(insee)
                gdf = self.fetch(geom)
            except Exception:
                self.log.warning("No GPU %s for %s", self.endpoint, insee)
                continue
            if gdf.empty:
                continue
            gdf["code_commune"] = insee
            keep = [c for c in ["code_commune", "libelle", "libelong", "typezone",
                                "destdomi", "partition", "captured_at", "geometry"] if c in gdf.columns]
            from rei.common.store import write_geo
            write_geo(gdf[keep], self.target_table, schema="gis")
            total += len(gdf)
            self.log.info("Loaded %d %s polygons for %s", len(gdf), self.endpoint, insee)
        return total


class ScotCollector(GpuCollector):
    """SCoT perimeters via GPU municipality endpoint."""
    source_id = "scot_documents"
    endpoint = "municipality"
    target_table = "scot"


class ZacCollector(GpuCollector):
    """ZAC/operation overlays from GPU prescription-surf."""
    source_id = "zac_operations"
    endpoint = "prescription-surf"
    target_table = "zac"
