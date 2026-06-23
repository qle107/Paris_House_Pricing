# IRIS Coverage & White-Area Audit

**Date:** 2026-06-23
**Scope:** Read-only audit. No code changed. No architecture redesigned.
**Question:** Why are large areas outside Paris white on the map?

---

## TL;DR — Root cause

The white areas are **not** a null-score, failed-join, filter, or rendering bug.
They are **un-ingested geography**: the pipeline only ever fetches and scores a
hard-coded **33-commune watchlist** (the 20 Paris arrondissements + 13
petite-couronne communes). Everywhere else there is **no polygon at all**, so the
CARTO basemap shows through as white.

Of the six hypotheses posed:

| Hypothesis | Verdict |
|---|---|
| Data does not exist | ❌ It exists publicly, nationally (49,420 IRIS) |
| **Data exists but is not loaded** | ✅ **This is the cause** — only 33 communes ingested |
| Data exists but is not scored | ❌ 100% of loaded IRIS are scored (0 nulls) |
| Data exists but is not rendered | ❌ 100% of scored IRIS are exported & rendered |
| Data exists but fails a join | ❌ Geometry↔score join is 100% |
| Data exists but is filtered out | ⚠️ Only at *fetch time* (`where com_code IN watchlist`), not post-load |

Within the loaded extent there are **zero white polygons**. The map is white
outside Paris because the data for those areas was never downloaded.

---

## Step 1 — Geographic dataset inventory

All geometry is stored as GeoParquet in `data/geo/`, all in **EPSG:4326**.

| Dataset | File | Source | Features | Geometry | Coverage |
|---|---|---|---|---|---|
| Communes | `data/geo/communes.parquet` | geo.api.gouv.fr (`admin_communes`) | 33 | MultiPolygon | **Paris + petite couronne** |
| IRIS (geometry) | `data/geo/iris.parquet` | ODS `georef-france-iris` (`iris_contours`) | 1,328 | Polygon (1,319) / MultiPolygon (9) | **33 communes** (dept 75/92/93/94) |
| IRIS (scored) | `data/geo/iris_scored.parquet` | derived (`rei/scoring/iris_engine.py`) | 1,328 | Polygon/MultiPolygon | same 33 communes |
| Zoning (PLU) | `data/geo/zoning.parquet` | GPU apicarto (`gpu_zoning`) | 1,169 | MultiPolygon | subset of the 33 |
| Parcels | `data/geo/parcels.parquet` | cadastre Etalab (`cadastre_parcels`) | 160,808 | Polygon | 33 communes |
| Buildings | `data/geo/buildings.parquet` | cadastre Etalab | 241,669 | MultiPolygon | 33 communes |

Score-driving tables (`data/tables/`):

| Table | Rows | Geo key | Distinct geos | Note |
|---|---|---|---|---|
| `iris_score` | 1,328 | iris_code/code_commune | 33 communes | matches geometry exactly |
| `dvf_transactions` | (per-commune CSV→parquet) | code_commune | 33 | per-commune fetch |
| `demographics` | 33 | geo_code | 33 | **single year (2023)** → no CAGR |
| `income` | 33 | geo_code | 33 | single year (2023) |
| `permits` | 2,080 | code_commune | **13** (92/93/94 only) | no Paris |
| `rents` | 33 | code_commune | 33 | |

The source registry (`config/sources.yaml`) lists every feed as **national**
(`granularity: IRIS` / `commune`). The collectors are national-capable; the
**inputs** are what restrict them to 33 communes.

---

## Step 2 — Geographic coverage (bounding boxes)

Every layer's bbox is the same tight Paris-core rectangle:

| Layer | lon min | lon max | lat min | lat max | Coverage class |
|---|---|---|---|---|---|
| communes | 2.2229 | 2.5655 | 48.7787 | 48.9740 | Paris + petite couronne |
| iris | 2.2229 | 2.5655 | 48.7787 | 48.9521 | Paris + petite couronne |
| iris_scored | 2.2229 | 2.5655 | 48.7787 | 48.9521 | Paris + petite couronne |
| parcels | 2.2242 | 2.5655 | 48.7787 | 48.9740 | Paris + petite couronne |
| zoning | 2.2363 | 2.4237 | 48.8068 | 48.9183 | subset of the above |

For reference, full coverage would span roughly:
**Île-de-France** ≈ lon [1.4, 3.6], lat [48.1, 49.2] ·
**France métropolitaine** ≈ lon [-5.2, 9.6], lat [41.3, 51.1].

**Coverage = Paris + petite couronne only.** ☐ Paris ☑ Petite couronne ☐ Île-de-France ☐ France

---

## Step 3 — IRIS coverage

```
IRIS features        : 1328
unique iris_code     : 1328
unique code_commune  : 33
departments          : 75, 92, 93, 94   (Paris + petite couronne)
```

Sample records:

```json
{ "iris_code": "751010303", "iris_name": "Palais Royal 3",  "code_commune": "75101" }
{ "iris_code": "751010105", "iris_name": "Tuileries",        "code_commune": "75101" }
{ "iris_code": "751010101", "iris_name": "Saint-Germain l'Auxerrois 1", "code_commune": "75101" }
```

Communes covered (all 33): `75101–75120` (Paris) + `92007, 92012, 92040, 92044,
92051, 93048, 93055, 93066, 93070, 94017, 94041, 94076, 94080`.

**Determination:** IRIS exists **only inside Paris + 13 petite-couronne communes.**
Not IDF-wide. Not national.

---

## Step 4 — Statistical / join coverage

Geometry ↔ score join (within the loaded extent):

```
iris geometry features   : 1328
iris_score table rows     : 1328
iris_scored geo features  : 1328
geometry iris_code in score table : 1328 / 1328
geometry NOT in score table       : 0
score rows NOT in geometry         : 0
Geometry <-> Score match %         : 100.0%
```

Null scores inside `iris_scored`:

```
score_total          : 0 null / 1328  (0.0%)
institutional_score  : 0 null / 1328  (0.0%)
alpha_score          : 0 null / 1328  (0.0%)
```

The join is perfect because geometry and scores are produced by the **same
pipeline keyed on `iris_code`** — there is no cross-dataset join to fail. Missing
input feeds do not break scoring: `score_iris()` scores each component on
whatever columns are present and **defaults a component to a neutral 50 when no
data is available** (`rei/scoring/iris_engine.py:115–118`). So an IRIS never comes
out white/grey for lack of a feed.

---

## Step 5 — White polygons

Polygons with **visible geometry AND null score**:

```
White polygons: 0
```

There are no white-by-null polygons. The map even renders a null score as **grey
`#cccccc`**, not white (`dashboards/map/index_files.html:76–77`), and zero
features hit that branch.

What the browser actually receives (`webmap/iris.geojson`):

```
rendered features              : 1328
unique communes rendered       : 33
rendered features w/ null score : 0
rendered bbox lon [2.223, 2.565] lat [48.779, 48.952]
```

**The "white" is everything outside that 1,328-polygon footprint — areas with no
geometry at all.** Quantified as missing IRIS:

| Target | Available (public) | Loaded | Missing (white) | % white |
|---|---|---|---|---|
| Île-de-France | **5,264** | 1,328 | **3,936** | 75% |
| France | **49,420** | 1,328 | **48,092** | 97.3% |

(Available counts queried live from the project's own source —
`georef-france-iris`, region 11 and national — see Step 6.)

---

## Step 6 — Does the data exist publicly?

Verified against the live sources the project already references (not guessed):

| Dataset | Exists | Coverage | Source (verified) |
|---|---|---|---|
| IRIS boundaries | **Yes** | France: **49,420** IRIS · IDF: **5,264** | ODS `georef-france-iris` API `total_count` (live) |
| Commune boundaries | **Yes** | National (~34,900 communes) | geo.api.gouv.fr (already used) |
| Population | **Yes** | National, IRIS-level (RP census) | INSEE Recensement |
| Income | **Yes** | National at commune level; **IRIS only for communes ≥5,000 hab** | INSEE FiLoSoFi |
| Housing / transactions | **Yes** | National (métropole + DOM, excl. Mayotte & Alsace-Moselle) | DGFiP DVF géolocalisées |
| Rents | **Yes** | National, commune-level | ANIL "carte des loyers" |

Live API checks performed:
- `georef-france-iris/records?limit=0` → `total_count: 49420` (national)
- `…?where=reg_code="11"&limit=0` → `total_count: 5264` (Île-de-France)

**Caveat (FiLoSoFi):** IRIS-level income only exists for communes ≥5,000
inhabitants. Smaller communes have no IRIS income — they degrade to commune-level
income / neutral. This is a data-availability limit, not a blocker for removing
white.

---

## Step 7 — Why areas are white (exact root cause)

1. `main.py` defines a hard-coded **`WATCHLIST` of 33 INSEE codes** (lines 19–24:
   `75101`…`75120`, plus 13 codes in 92/93/94).
2. `run_pipeline()` passes that list straight into every collector as
   `communes=communes` (`main.py:70–81`).
3. `IrisContoursCollector.collect()` loops **`for code in communes`** and queries
   OpenDataSoft with `where com_code="{code}" or com_arm_code="{code}"`
   (`rei/ingestion/iris.py:24,29`). It therefore downloads IRIS **only for the 33
   watchlist communes** → 1,328 polygons.
4. `DvfCollector`, `CadastreCollector`, `GpuCollector` are likewise driven
   per-commune by the same list.
5. `score_iris()` scores exactly what was ingested → 1,328 IRIS, all non-null.
6. `export_geojson()` writes all 1,328 to `webmap/iris.geojson`; the map fits its
   viewport to that extent (`index_files.html:214–220`).

> IRIS polygons exist nationally (49,420). The pipeline loads only the 33-commune
> watchlist (1,328 IRIS). The remaining ~48,092 IRIS in France (3,936 in IDF
> alone) are never downloaded, so they render as white basemap — **not** because
> `score = null`, but because **geometry = absent**.

Confirming it is *not* the other failure modes: join = 100%, null scores = 0,
rendered nulls = 0, and the export/scoring/map code is coverage-agnostic
(everything is keyed on whatever communes are fed in; nothing hardcodes Paris
downstream).

---

## Step 8 — Minimal fix (recommended, not implemented)

The whole pipeline is already coverage-agnostic; **only the input commune list
and one per-commune collector constrain it to Paris.** Keep the architecture.

### A. 100% Île-de-France coverage

Smallest change that removes all IDF white:

1. **`main.py`** — drive ingestion by the 8 IDF departments
   (`75, 77, 78, 91, 92, 93, 94, 95`) instead of the 33-code `WATCHLIST`.
2. **`rei/ingestion/iris.py`** — add a department/region bulk path mirroring what
   `admin_boundaries.py` already does, so IRIS is fetched with one paged query
   (`where reg_code="11"`, ~53 pages of 100) instead of 1,287 per-commune calls.
   (~10–15 lines.)
3. **`admin_communes`** — already supports `departements=[…]`
   (`rei/ingestion/admin_boundaries.py:29–38`); just call it with the 8 depts. No code change.
4. *(Optional, for meaningful — not just neutral — scores)*
   **`rei/ingestion/dvf.py`** — add the per-**department** DVF file path
   (`/{year}/departements/{dep}.csv`) so DVF is 8 files/year, not ~1,287
   per-commune fetches. (~15 lines.)
5. Re-run `python main.py --score-level iris`. **`export.py`, `iris_engine.py`,
   `files_engine.py`, the map HTML — unchanged.**

- **Files to change:** 2 required (`main.py`, `iris.py`); 1 optional (`dvf.py`).
- **Datasets:** georef-france-iris (region 11 → 5,264 IRIS), geo.api.gouv.fr (8 depts),
  + national INSEE pop/income/rents tables; DVF dept files for real scores.
- **Effort:** ~½ day. Output GeoJSON (~5,264 simplified polygons) is a few MB — fine in-browser.

Even with **no** DVF, expanding the IRIS input alone makes all 5,264 IDF IRIS
render (scores neutral-ish where feeds are absent) — i.e. **white disappears
immediately**; richer feeds only improve the *values*, not the coverage.

### B. 100% France coverage

Same code paths, larger pulls:

1. **`iris.py`** — loop all 18 regions (or 101 departments); ~494 paged ODS
   requests → 49,420 IRIS.
2. **`admin_communes`** — national mode already exists (call with no args).
3. **`dvf.py`** — per-department bulk becomes **mandatory** (101 files/year;
   per-commune ×34,900 is infeasible).
4. National INSEE pop/income/rents tables.
5. **Leave cadastre / zoning / buildings out** of the national rollout — they are
   heavy and only feed the development/supply components, which degrade to neutral.
   Not needed to remove white.

- **Files to change:** `main.py`, `iris.py`, `dvf.py` (same three).
- **Effort:** ~1–2 days incl. runtime/storage.
- **⚠️ Rendering scalability (flag, beyond "de-white"):** a 49,420-polygon
  GeoJSON is tens of MB and will choke MapLibre as a single source. For national
  production, switch the IRIS layer to **vector tiles** (tippecanoe → PMTiles, or
  server-side tiles via the existing `rei/api/tiles.py`). This is a separate
  rendering task, not part of the minimal coverage fix.

---

## Deliverables index

- **Coverage map summary** — Steps 2, 3 (Paris + petite couronne; 33 communes; dept 75/92/93/94).
- **Dataset inventory** — Step 1.
- **Join diagnostics** — Step 4 (100% geometry↔score; 0 null).
- **Missing-feature diagnostics** — Step 5 (0 white-by-null; 3,936 IDF / 48,092 FR IRIS un-ingested).
- **Root cause** — Step 7 (hard-coded watchlist + per-commune IRIS fetch).
- **Exact code files** — `main.py` (WATCHLIST 19–24; pass-through 70–81),
  `rei/ingestion/iris.py` (24, 29), `rei/ingestion/dvf.py` (28–30, 68–77),
  `rei/ingestion/admin_boundaries.py` (29–38, already multi-scope),
  `rei/api/export.py` (coverage-agnostic), `rei/scoring/iris_engine.py` (115–118 neutral fallback),
  `dashboards/map/index_files.html` (76–77 null→grey; 214–220 fit-to-extent).
- **Minimal fix plan** — Step 8.

### Minor observations (not causes of white areas)
- `demographics` and `income` hold a **single year (2023)** for only the 33
  communes, so growth components (`pop_cagr`, `income_growth`) are neutral
  everywhere. Multi-year pulls are needed for meaningful growth scores (already
  noted in `IRIS_AUDIT.md`).
- `data/tables/dvf_transactions.parquet` and `commune_score.parquet` could not be
  opened by the sandbox's `pyarrow` ("Parquet magic bytes not found"). The
  pipeline reads them via its own store, so this is likely a writer/engine
  version quirk worth a quick check — unrelated to the white-area question.
