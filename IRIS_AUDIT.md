# IRIS audit

**Date:** 2026-06-23

## Summary

IRIS support is implemented end-to-end (loader, scorer, exporter, map). Geometry exists in `data/geo/iris.parquet` (1,328 polygons). The choropleth was empty because `score_iris()` crashed before writing `iris_scored` / `iris.geojson`. Root cause: `_long_cagr` returned an empty frame without columns when demographics had only one year per commune.

## Code map

| File | Role |
|------|------|
| `rei/ingestion/iris.py` | Load OpenDataSoft contours → `data/geo/iris.parquet` |
| `config/sources.yaml` | `iris_contours` registry entry |
| `rei/scoring/iris_engine.py` | `score_iris()` → `iris_score`, `iris_scored` |
| `rei/api/export.py` | Export `iris_scored` → `webmap/iris.geojson` |
| `main.py` | Ingest + score when `--score-level iris` |
| `dashboards/map/index_files.html` | IRIS choropleth layer |

## Geometry

```
features:   1328
CRS:        EPSG:4326
fields:     iris_code, iris_name, code_commune, geometry
```

## Why the map was blank

1. `export_geojson` reads `iris_scored`.
2. `iris_scored` was never written — scoring failed.
3. `HEAD ./iris.geojson` → 404 → map skips IRIS layers.

## Join check

Scores and geometry share `iris_code` from the same pipeline. No separate join step.

## Root cause

`assemble_features()` → `_long_cagr()` with single-year demographics → empty DataFrame without `code_commune` → merge KeyError.

**Fix:** `_long_cagr` returns `pd.DataFrame(rows, columns=["code_commune", out])`.

## Next steps

1. Run `python main.py --score-level iris`.
2. Confirm `data/geo/iris_scored.parquet` and `webmap/iris.geojson` exist.
3. Wire missing feeds (multi-year INSEE, transit distances, parcel FAR) into existing score slots.

## Feed gaps (IRIS institutional scores)

| Area | Gap |
|------|-----|
| Growth | Single-year population/income — no CAGR yet |
| Accessibility | GTFS/GPE opt-in; distance fields are stubs |
| Development | Parcel FAR not computed in file mode |
| Supply | Sitadel collector needs DiDo filter verification |
