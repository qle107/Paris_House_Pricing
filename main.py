#!/usr/bin/env python3
"""One-command file-mode pipeline + map. Run: python main.py"""
from __future__ import annotations

import argparse
import functools
import http.server
import os
import shutil
import socketserver
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# Set file storage before importing rei.
os.environ.setdefault("REI_STORAGE", "files")
os.environ.setdefault("REI_DATA_DIR", str(ROOT / "data"))

WATCHLIST = [
    "75101", "75102", "75103", "75104", "75105", "75106", "75107", "75108", "75109", "75110",
    "75111", "75112", "75113", "75114", "75115", "75116", "75117", "75118", "75119", "75120",
    "93066", "93070", "94076", "92007", "94017",
    "92012", "92044", "92051", "92040", "93048", "93055", "94041", "94080",
]

GEO_SOURCES = ["admin_communes", "dvf_transactions"]
PARCEL_SOURCES = ["cadastre_parcels", "gpu_zoning"]
TABULAR_SOURCES = ["insee_population", "insee_income", "sitadel_permits", "rental_observatoires"]


def _run(source_id: str, **kwargs):
    from rei.ingestion.registry import get_collector
    try:
        n = get_collector(source_id).run(**kwargs)
        print(f"  [ok]   {source_id}: {n} rows")
    except Exception as exc:
        print(f"  [warn] {source_id}: {exc}")


def run_pipeline(communes, skip_ingest, profile, with_transit, with_parcels, score_level):
    from rei.api.export import export_geojson
    from rei.common.store import using_files
    from rei.scoring.files_engine import score

    if not skip_ingest:
        print("== Ingesting ==")
        for sid in GEO_SOURCES:
            _run(sid, communes=communes)
        if score_level == "iris":
            _run("iris_contours", communes=communes)
        if with_parcels:
            for sid in PARCEL_SOURCES:
                _run(sid, communes=communes)
        for sid in TABULAR_SOURCES:
            _run(sid, communes=communes)
        if with_transit:
            _run("transit_gtfs", area_query="Ile-de-France")
        if with_parcels:
            if using_files():
                print("== Skipping parcel buildable-upside (PostGIS only) ==")
            else:
                from rei.gis.persist import compute_and_store_upside
                print("== Computing parcel buildable-upside ==")
                for c in communes:
                    try:
                        compute_and_store_upside(c)
                    except Exception as exc:
                        print(f"  [warn] upside {c}: {exc}")

    print("== Scoring communes 0-100 (fallback layer) ==")
    try:
        result = score(profile)
        if not result.empty:
            print(result[["code_commune", "name", "attractiveness_score", "rank"]].head(10).to_string(index=False))
    except Exception as exc:
        print(f"  [warn] scoring: {exc}")

    if score_level == "iris":
        print("== Scoring IRIS 0-100 (primary) ==")
        try:
            from rei.scoring.iris_engine import score_iris
            ir = score_iris()
            if not ir.empty:
                print(ir.sort_values("score_total", ascending=False)
                      [["iris_code", "iris_name", "score_total", "rank"]].head(10).to_string(index=False))
        except Exception as exc:
            print(f"  [warn] iris scoring: {exc}")

    print("== Exporting GeoJSON for the map ==")
    webmap = ROOT / "webmap"
    webmap.mkdir(exist_ok=True)
    written = export_geojson(webmap)
    shutil.copyfile(ROOT / "dashboards" / "map" / "index_files.html", webmap / "index.html")
    return webmap, written


def serve(webmap: Path, port: int):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(webmap))
    with socketserver.TCPServer(("", port), handler) as httpd:
        url = f"http://localhost:{port}"
        print(f"\nMap ready at {url}   (Ctrl+C to stop)")
        try:
            webbrowser.open(url)
        except Exception:
            pass
        httpd.serve_forever()


def main():
    ap = argparse.ArgumentParser(description="France RE pipeline + map (file mode)")
    ap.add_argument("--communes", default=",".join(WATCHLIST), help="comma-separated INSEE codes")
    ap.add_argument("--profile", default="value_add_opportunistic")
    ap.add_argument("--score-level", choices=["iris", "commune"], default="iris",
                    help="primary scoring grain; iris adds sub-commune detail (commune kept as fallback)")
    ap.add_argument("--skip-ingest", action="store_true", help="reuse files already in ./data")
    ap.add_argument("--with-parcels", action="store_true", help="also ingest cadastre+zoning and compute parcel upside (heavy)")
    ap.add_argument("--with-transit", action="store_true", help="also download GTFS (large)")
    ap.add_argument("--no-serve", action="store_true", help="build files only, don't serve")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    communes = [c.strip() for c in a.communes.split(",") if c.strip()]

    print(f"Storage = files  |  data dir = {os.environ['REI_DATA_DIR']}")
    print(f"Watchlist = {communes}\n")
    webmap, written = run_pipeline(communes, a.skip_ingest, a.profile, a.with_transit, a.with_parcels, a.score_level)
    print(f"\nWrote map layers {written} -> {webmap}")
    print(f"Scores CSV -> {Path(os.environ['REI_DATA_DIR']) / 'tables' / 'commune_score.csv'}")
    if not a.no_serve:
        serve(webmap, a.port)
    else:
        print(f"Open {webmap / 'index.html'} via a local server (e.g. `python -m http.server -d webmap`).")


if __name__ == "__main__":
    main()
