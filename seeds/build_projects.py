"""Export the verified Grand Paris core project seeds to GeoJSON deliverables.

Run from the repo root::

    python seeds/build_projects.py

Writes ``seeds/transport_projects.geojson`` and ``seeds/development_projects.geojson``.
The canonical data lives in ``rei/transport/projects.py`` and
``rei/development/projects.py``; this script is just a portable export (the GeoJSON
files are git-ignored like the rest of ``*.geojson`` and regenerated on demand).
"""
from __future__ import annotations

from pathlib import Path

from rei.development.projects import seed_frame as dev_seed
from rei.transport.projects import seed_frame as transport_seed

OUT = Path(__file__).resolve().parent


def _dump(gdf, name: str) -> tuple[Path, int]:
    g = gdf.copy()
    for col in g.columns:                       # GeoJSON wants ISO strings, not date objects
        if col != "geometry" and g[col].map(lambda v: hasattr(v, "isoformat")).any():
            g[col] = g[col].astype(str)
    path = OUT / f"{name}.geojson"
    g.to_file(path, driver="GeoJSON")
    return path, len(g)


def main() -> None:
    for frame, name in ((transport_seed(), "transport_projects"),
                        (dev_seed(), "development_projects")):
        path, n = _dump(frame, name)
        print(f"wrote {n:3d} features -> {path.relative_to(OUT.parent)}")


if __name__ == "__main__":
    main()
