# IRIS scoring architecture

Primary spatial unit: **IRIS** (~2,000 residents). Commune scoring remains as fallback.

**File mode (current):** `python main.py`, producing Parquet/GeoParquet + GeoJSON + MapLibre.

**PostGIS mode:** materialized views + MVT tiles for scale and parcel detail.

Hierarchy: Region → Department → Commune → IRIS → Parcel.

---

## Schema (PostGIS)

```sql
CREATE TABLE gis.iris (
  iris_code     text PRIMARY KEY,
  iris_name     text,
  code_commune  text NOT NULL,
  com_arm_code  text,
  geometry      geometry(MultiPolygon,4326)
);
CREATE INDEX iris_geom_gix ON gis.iris USING GIST (geometry);

CREATE TABLE scores.iris_score (
  iris_code           text REFERENCES gis.iris(iris_code),
  profile             text NOT NULL,
  score_demographics  numeric, score_economics   numeric,
  score_housing       numeric, score_supply      numeric,
  score_accessibility numeric, score_development numeric,
  score_total         numeric, rank int, hotspot_tier int,
  PRIMARY KEY (iris_code, profile)
);

ALTER TABLE gis.parcels ADD COLUMN iris_code text REFERENCES gis.iris(iris_code);
```

File equivalents: `data/geo/iris.parquet`, `data/geo/iris_scored.parquet`, `data/tables/iris_score.csv`.

## Migration steps

1. Apply DDL above.
2. Run `iris_contours` ingestion.
3. Backfill `parcels.iris_code` via centroid join.
4. Set `score_level=iris` (default); commune scoring unchanged.
5. Run `score_iris()`.

## Ingestion

| Feed | Source | Notes |
|------|--------|-------|
| IRIS boundaries | OpenDataSoft `georef-france-iris` | Match `com_code` or `com_arm_code` |
| Demographics/income | INSEE Melodi | IRIS where available; else commune |
| Housing | DVF point-in-polygon | Per IRIS |
| Zoning | GPU `zone-urba` | Intersect with IRIS |

## Spatial joins

- **DVF → IRIS:** point within polygon (GiST / `sjoin`).
- **Parcel → IRIS:** centroid containment; store `iris_code`.
- Metric CRS: EPSG:2154; storage/serving: 4326.

## Scoring

`rei/scoring/iris_engine.py` blends six components, percentile 0–100, missing → 50:

```
IRIS_SCORE = 0.15*demographics + 0.20*economics + 0.20*housing
           + 0.15*supply + 0.15*accessibility + 0.15*development
```

| Component | Inputs today |
|-----------|--------------|
| demographics | pop CAGR (commune); rest neutral |
| economics | income (commune); rest neutral |
| housing | DVF per IRIS |
| supply | AU share per IRIS |
| accessibility | stubs (GTFS/GPE not wired) |
| development | stubs (parcel metrics not wired) |

Institutional sub-scores: `rei/scoring/institutional.py` (optional merge).

## API / map

- File mode: `export_geojson()` → `iris.geojson`.
- PostGIS: `/api/iris/{code}`, `/tiles/iris/{z}/{x}/{y}.mvt`.
- Map: IRIS choropleth default; commune layer as toggle; hotspots by `hotspot_tier`.

## Performance

- File mode: simplify geometry on export (~10 m).
- PostGIS: MVT + GiST indexes + zoom-based simplification.

## Rollout

1. File mode with `--score-level iris` (done).
2. Validate watchlist coverage.
3. Wire GTFS, parcel FAR, IRIS-native INSEE feeds.
4. Enable PostGIS tiles for national scale.

## File-mode limits

- Demographics/economics/rent are commune-level until IRIS feeds land.
- Accessibility and development score 50 (neutral) until wired.
- Parcel popups need PostGIS/MVT path.
