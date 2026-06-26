# Data architecture — Bronze / Silver / Gold (Medallion)

This project follows the **Medallion** pattern (Bronze → Silver → Gold), the same
layering used by the EFREI *Urban Data Explorer* group project. REI keeps the same
three responsibilities but uses its own storage: it runs either on local
Parquet/GeoParquet files (`REI_STORAGE=files`, the default for `python main.py`) or
on PostgreSQL + PostGIS in production (`REI_STORAGE=postgres`). The layer a dataset
belongs to is about its *role*, not its file extension.

## The rule

| Layer | Role | Mutable source of truth? |
|-------|------|--------------------------|
| **Bronze** | Raw, untouched downloads exactly as the provider served them. | No — re-downloadable. |
| **Silver** | Cleaned, typed, filtered feeds. One tidy table/layer per source. Never hand-edited. | No — regenerated from Bronze. |
| **Gold** | Computed indicators and final scores that the map and API consume. | Yes — the published product. |

Bronze is disposable, Silver is reproducible, Gold is the deliverable. The whole
`data/` tree is git-ignored; `python main.py` regenerates it, and in Postgres mode
the `scores` schema is the shared source of truth (same idea as the school project's
"Gold = always in the DB").

## Where each layer lives in REI

| Layer | File mode (`REI_STORAGE=files`) | Postgres mode (`REI_STORAGE=postgres`) |
|-------|----------------------------------|-----------------------------------------|
| Bronze | `data/raw/` (e.g. `cadastre_parcels/`, `dvf_transactions/`) | `data/raw/` (download cache; not loaded as-is) |
| Silver | `data/tables/*.parquet` (tabular) and `data/geo/*.parquet` (GeoParquet) | schemas **`core`** (tabular feeds) and **`gis`** (spatial layers) |
| Gold | scored tables/layers in `data/tables/` + `data/geo/` (e.g. `iris_score`, `iris_scored`) | schema **`scores`** |
| Operational | `data/ingestion_log.csv` | schema **`meta`** (ingestion log, watermarks) |

Dispatch between the two backends is handled centrally by `rei/common/store.py`
(`write_table_files` / `write_geo` / `read_table` / `read_geo`), so collectors and
scorers do not care which backend is active.

## Dataset lineage by theme

Bronze source (registry id in `config/sources.yaml`) → Silver feed → Gold indicator.

| Theme | Bronze source | Silver (table / geo) | Gold indicator |
|-------|---------------|----------------------|----------------|
| Price / m² | `dvf_transactions` | `dvf_transactions` | `commune_score`, `iris_score` (Value / hedonic discount in `institutional`) |
| Demographics | `insee_population`, `insee_income` | `population`, `income` | demographics & economics components of `iris_score` |
| Supply / permits | `sitadel_permits`, `gpu_zoning` | `permits`, `zoning` (geo) | supply component, `future_development` |
| Transport | `transit_gtfs`, `transport_projects` | `transit_stops` (geo), `transport_projects` (geo) | `future_development` (catalysts) |
| Development | `cadastre_parcels`, `development_projects` | `parcels`, `buildings` (geo) | `future_development`, parcel upside |
| Risk | `georisques` | `risk` | climate haircut in `institutional` |
| **Schools** | **`schools_directory`** | **`school_points` (geo)** | **`accessibility.school_access_score`** |
| **Hospitals** | **`hospitals_finess`** | **`hospital_points` (geo)** | **`accessibility.hospital_access_score`** |
| **Social housing (SRU)** | **`social_housing_sru`** | **`social_housing`** | **`social_housing.{share, sru_deficit_pct}`** (broadcast to IRIS) |
| **Family liveability** | (derived) | `accessibility`, `crime` | **`liveability.family_liveability_score`** |
| Map geometry | `iris_contours`, `admin_communes` | `iris` (geo), `communes` (geo) | `iris_scored`, `communes` enriched |

The four rows in bold were added so REI covers the same themes as the school spec
(school accessibility, hospitals, social housing, family liveability). They follow
the existing per-IRIS pattern of `rei/scoring/future_development.py`.

## The new indicators in detail

All four are computed at the IRIS grain (≈1,300 Grand-Paris neighbourhoods) and run
in file mode without a database.

- **School & hospital accessibility** — `rei/scoring/accessibility_iris.py`.
  Reads the `school_points` / `hospital_points` geo layers, counts amenities within a
  walk/drive catchment of each IRIS centroid (1 km schools, 3 km hospitals),
  distance-decays them, and percentile-normalises to 0–100. A missing point layer
  yields NaN (dropped downstream) rather than a fake neutral score. Output:
  `data/tables/accessibility.parquet`.
- **Social housing (SRU)** — `rei/ingestion/social_housing.py`.
  Commune-level share of social housing from the loi-SRU (art. 55) inventory, with
  the legal target (25%) and the deficit. Broadcast to IRIS by `code_commune` (the
  same commune→IRIS broadcast the price forecast uses). Output:
  `data/tables/social_housing.parquet`.
- **Family liveability** — `rei/scoring/liveability.py`.
  Composite blending school access, healthcare access, safety (inverse recorded
  crime) and a Phase-2 amenities slot. Weights are **renormalised over whatever data
  is present** (the same `_wavg` used by the institutional suite), and each IRIS
  reports `liveability_coverage`. Output: `data/tables/liveability.parquet`.

All three are merged onto `iris.geojson` by `rei/api/export.py`, so the map can
colour by any of them, and are run from `main.py` in the IRIS scoring block.

## Mapping to the school's Bronze/Silver/Gold

If you need to answer "what is my Bronze/Silver/Gold?" in the school's own terms:

| School (Urban Data Explorer) | REI equivalent |
|------------------------------|----------------|
| `schools/*.xlsx` → `schools_merged.csv` → `schools_ref` (DB) | `schools_directory` → `school_points` (geo) → `accessibility` |
| `base-ic-evol-pop.CSV` → `population_paris.csv` → `population_ref` | `insee_population` → `population` → demographics component |
| `school_density` (Gold indicator, per IRIS) | `accessibility.school_access_score` (per IRIS) |
| `vivabilite_familiale_iris.csv` (Gold) | `liveability.family_liveability_score` (per IRIS) |
| hospitals / BDCOM / DVF "todo" Gold indicators | `accessibility.hospital_access_score`, `social_housing`, DVF `institutional` (already done) |
| MySQL `schools_ref`, `population_ref`, `school_density` | Postgres `scores` schema (or `data/tables/*.parquet` in file mode) |

## Adding another Gold indicator

1. Add the Bronze source to `config/sources.yaml` and a collector in `rei/ingestion/`.
2. Write a `rei/scoring/<indicator>.py` with a `run_files()` that reads from the store
   and writes `data/tables/<indicator>.parquet` via `store.write_table_files(...,
   conflict_cols=("iris_code",))` — model it on `future_development.py` or
   `accessibility_iris.py`.
3. Call it in the IRIS block of `main.py` and merge it onto `iris.geojson` in
   `rei/api/export.py`.
4. Add a unit test in `tests/` (synthetic frames, no network), as in
   `tests/test_accessibility_iris.py`.
