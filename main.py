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

# Geometry + scoring feeds are fetched IDF-wide (8 departments) so the map fills and
# scores vary across all of Ile-de-France. Parcels/zoning stay on WATCHLIST (heavy).
IDF_DEPARTEMENTS = ["75", "77", "78", "91", "92", "93", "94", "95"]
DVF_YEARS_DEFAULT = [2021, 2022, 2023, 2024, 2025]
PARCEL_SOURCES = ["cadastre_parcels", "gpu_zoning"]


def _run(source_id: str, **kwargs):
    from rei.ingestion.registry import get_collector
    try:
        n = get_collector(source_id).run(**kwargs)
        print(f"  [ok]   {source_id}: {n} rows")
    except Exception as exc:
        print(f"  [warn] {source_id}: {exc}")


def _choose_horizon(years, requested, min_base_years=3):
    """Largest horizon <= requested with >= min_base_years base years (so the model
    has several rows to learn from); else the largest feasible; None if < 2 years."""
    if len(years) < 2:
        return None
    yset = set(years)
    fallback = None
    for h in range(min(requested, years[-1] - years[0]), 0, -1):
        n_base = sum((y + h) in yset for y in years)
        if n_base >= 1 and fallback is None:
            fallback = h
        if n_base >= min_base_years:
            return h
    return fallback


def run_pipeline(communes, skip_ingest, profile, with_transit, with_parcels, score_level,
                 with_forecast=False, forecast_horizon=5, dvf_years=None,
                 refresh=False, retrain=False, with_listings=False):
    from rei.api.export import export_geojson
    from rei.common.store import geo_exists, table_exists, using_files
    from rei.scoring.files_engine import score

    data_present = (table_exists("dvf_transactions") and geo_exists("communes")
                    and (score_level != "iris" or geo_exists("iris")))
    do_ingest = (not skip_ingest) and (refresh or bool(dvf_years) or not data_present)
    if not do_ingest:
        print("== Skipping ingest (%s) ==" % ("--skip-ingest" if skip_ingest else "data present; use --refresh to refetch"))
    if do_ingest:
        print("== Ingesting (Ile-de-France) ==")
        _run("admin_communes", departements=IDF_DEPARTEMENTS)
        _run("dvf_transactions", departements=IDF_DEPARTEMENTS, years=(dvf_years or DVF_YEARS_DEFAULT))
        if score_level == "iris":
            _run("iris_contours", departements=IDF_DEPARTEMENTS)
        if with_parcels:
            for sid in PARCEL_SOURCES:
                _run(sid, communes=communes)
        # Scoring feeds, IDF-wide: income/population via bulk Melodi sweep, rents from
        # the national carte-des-loyers filtered to IDF. Permits stay commune-level.
        _run("insee_population", departements=IDF_DEPARTEMENTS)
        _run("insee_income", departements=IDF_DEPARTEMENTS)
        _run("rental_observatoires", departements=IDF_DEPARTEMENTS)
        _run("sitadel_permits", communes=communes)
        _run("georisques", communes=communes)   # natural-hazard overlay -> climate haircut
        # Forward-looking project pipeline (verified Grand Paris core seed; light, keyless).
        _run("transport_projects")
        _run("development_projects")
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

        print("== Scoring future development (per-IRIS) ==")
        try:
            from rei.scoring.future_development import run_files as score_future_dev
            n = score_future_dev()
            print(f"  future_development: {n} IRIS scored")
        except Exception as exc:
            print(f"  [warn] future development: {exc}")

    if with_forecast:
        from rei.ml.predict import predict_all
        from rei.ml.train import MODEL_PATH, train
        should_train = retrain or do_ingest or not MODEL_PATH.exists()
        ok = True
        try:
            if should_train:
                from rei.ml.features import load_price_long
                years = sorted(load_price_long()["year"].unique().tolist())
                h = _choose_horizon(years, forecast_horizon)
                if h is None:
                    print(f"== Forecast skipped: need >= 2 years of DVF (found {years or 'none'}); "
                          "re-run with --dvf-years 2020,2021,2022,2023,2024,2025 --refresh ==")
                    ok = False
                else:
                    n_base = sum((y + h) in set(years) for y in years)
                    note = "" if n_base >= 3 else "  [thin history -> forecast may be near-uniform; add --dvf-years]"
                    print(f"== Training price-growth model (DVF {years[0]}-{years[-1]}, horizon={h}y, {n_base} base year(s)){note} ==")
                    metrics = train(horizon=h)
                    print(f"  model: MAE={metrics.get('mae'):.4f}  80%-coverage={metrics.get('interval_coverage_80'):.2f}  n_train={metrics.get('n_train')}")
            else:
                print("== Forecasting (reusing saved model; --retrain to refit) ==")
            if ok:
                fc = predict_all(with_shap=True)
                if not fc.empty:
                    print(fc.head(10)[["code_commune", "expected_price_cagr", "cagr_p10", "cagr_p90"]].to_string(index=False))
        except Exception as exc:
            print(f"  [warn] forecast: {exc}")

    if with_listings:
        print("== Ingesting property listings (provider=%s) ==" % os.environ.get("REI_LISTINGS_PROVIDER", "sample"))
        _run("listings")

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
    ap.add_argument("--with-forecast", action="store_true",
                    help="train/reuse a price-growth model and show the forecast in the map popups")
    ap.add_argument("--forecast-horizon", type=int, default=5,
                    help="max years ahead; auto-reduced to fit the available DVF history")
    ap.add_argument("--dvf-years", default=None,
                    help="comma-separated DVF years to ingest, e.g. 2020,2021,2022,2023,2024,2025 (default: last 2)")
    ap.add_argument("--refresh", action="store_true", help="re-fetch sources even if local data already exists")
    ap.add_argument("--retrain", action="store_true", help="refit the forecast model even if a saved one exists")
    ap.add_argument("--with-listings", action="store_true",
                    help="ingest property listings as map points (sample provider by default; see LISTINGS_FEASIBILITY.md)")
    ap.add_argument("--no-serve", action="store_true", help="build files only, don't serve")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    communes = [c.strip() for c in a.communes.split(",") if c.strip()]

    print(f"Storage = files  |  data dir = {os.environ['REI_DATA_DIR']}")
    print(f"Watchlist = {communes}\n")
    dvf_years = [int(y) for y in a.dvf_years.split(",")] if a.dvf_years else None
    webmap, written = run_pipeline(communes, a.skip_ingest, a.profile, a.with_transit, a.with_parcels,
                                   a.score_level, a.with_forecast, a.forecast_horizon, dvf_years,
                                   a.refresh, a.retrain, a.with_listings)
    print(f"\nWrote map layers {written} -> {webmap}")
    print(f"Scores CSV -> {Path(os.environ['REI_DATA_DIR']) / 'tables' / 'commune_score.csv'}")
    if not a.no_serve:
        serve(webmap, a.port)
    else:
        print(f"Open {webmap / 'index.html'} via a local server (e.g. `python -m http.server -d webmap`).")


if __name__ == "__main__":
    main()
