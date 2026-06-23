"""GTFS transit stops and transport project loading."""
from __future__ import annotations

import io
import zipfile

import geopandas as gpd
import pandas as pd

from rei.common.db import get_engine, upsert_dataframe
from rei.ingestion.base import Collector

PAN = "https://transport.data.gouv.fr/api"


class GtfsCollector(Collector):
    source_id = "transit_gtfs"
    rps = 4.0

    def list_feeds(self) -> list[dict]:
        return self.http.get_json(f"{PAN}/datasets")

    def find_gtfs_url(self, dataset_id: str) -> str | None:
        ds = self.http.get_json(f"{PAN}/datasets/{dataset_id}")
        for r in ds.get("resources", []):
            if (r.get("format") or "").upper() == "GTFS" and r.get("url"):
                return r["url"]
        return None

    def load_stops(self, gtfs_url: str, network: str) -> int:
        resp = self.http.get(gtfs_url)
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            with zf.open("stops.txt") as fh:
                stops = pd.read_csv(fh)
        stops = stops.dropna(subset=["stop_lat", "stop_lon"])
        gdf = gpd.GeoDataFrame(
            {
                "network": network,
                "stop_id": stops["stop_id"].astype(str),
                "stop_name": stops.get("stop_name"),
            },
            geometry=gpd.points_from_xy(stops["stop_lon"], stops["stop_lat"]),
            crs=4326,
        )
        from rei.common.store import write_geo
        write_geo(gdf, "transit_stops", schema="gis", key="stop_id")
        self.log.info("Loaded %d stops for %s", len(gdf), network)
        return len(gdf)

    def collect(self, dataset_ids: list[str] | None = None, area_query: str | None = None) -> int:
        if not dataset_ids:
            feeds = self.list_feeds()
            if area_query:
                feeds = [f for f in feeds if area_query.lower() in str(f.get("title", "")).lower()]
            dataset_ids = [f["id"] for f in feeds if (f.get("type") == "public-transit")]
        total = 0
        for ds_id in dataset_ids:
            url = self.find_gtfs_url(ds_id)
            if url:
                total += self.load_stops(url, network=ds_id)
        return total


class ProjectCollector(Collector):
    """Curated transport projects from a GeoJSON/CSV file."""
    source_id = "transport_projects"

    def collect(self, geojson_path: str | None = None) -> int:
        if not geojson_path:
            raise ValueError("Provide a curated transport_projects GeoJSON/CSV path")
        gdf = gpd.read_file(geojson_path).to_crs(4326)
        from rei.common.store import write_geo
        write_geo(gdf, "transport_projects", schema="gis")
        return len(gdf)
