"""Forward-looking urban-development projects (ZAC, districts, public facilities)."""
from __future__ import annotations

import geopandas as gpd

from rei.ingestion.base import Collector


class DevelopmentProjectsCollector(Collector):
    """Major aménagement operations and large facilities for the Grand Paris core.

    With no path, loads the verified seed (``rei.development.projects.seed_frame``);
    a GeoJSON/CSV path (e.g. GPU/ZAC perimeters exported from API Carto) overrides it.
    """
    source_id = "development_projects"

    def collect(self, geojson_path: str | None = None) -> int:
        if geojson_path:
            gdf = gpd.read_file(geojson_path).to_crs(4326)
        else:
            from rei.development.projects import seed_frame
            gdf = seed_frame()
        from rei.common.store import write_geo
        return write_geo(gdf, "development_projects", schema="gis", key="project")
