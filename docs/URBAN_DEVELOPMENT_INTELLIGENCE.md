# Future urban-development intelligence: gap analysis and dataset

Date: 2026-06-24

Scope: Grand Paris core -- Paris (75), Hauts-de-Seine (92), Seine-Saint-Denis
(93), Val-de-Marne (94). Categories: transport (metro/RER/tram/hubs), master
plans and rezoning (ZAC/PLU/SCoT), major construction and new districts, and
public facilities.

## Summary

The zone-evaluation model scores neighbourhoods on what they are today. It had no
forward-looking layer: a zone that is unattractive now but sits on a Grand Paris
Express station or a 400,000 m2 ZAC opening in three years was scored as if
nothing were coming. This work fills that gap with a verified dataset of planned
projects, an impact model, and the wiring to feed a per-IRIS future-development
indicator into scoring.

The important finding is that the gap was data, not code. The repository already
had the scaffolding -- a `gis.transport_projects` table, a parcel-level transport
uplift model (`rei/transport/impact.py`), a density-change signal that reads
transport commitments and rezoning (`rei/zoning/detectors.py`), and ZAC/SCoT
collectors -- but every one of those inputs was empty or a stub. The registry
listed `transport_projects`, `zac_operations`, `scot_documents` and
`regional_plans` as `scaffold`, and the only transport seed in code was seven
hard-coded Grand Paris Express lines with no station coordinates and dates that
had since slipped by up to two years.

## What was missing

| Need (from the brief) | Before | Status now |
|---|---|---|
| Planned projects, next 5-10 years | 7 hard-coded GPE lines, no geometry | 46 transport + 15 development records, geocoded |
| Master plans / rezoning (ZAC/PLU/SCoT) | collectors present, tier `scaffold`, no data | ZAC/district layer seeded; GPU collectors documented for refresh |
| Public-transport projects under construction | dates stale (e.g. "2026" for lines now 2027-2031) | June-2026 status and dates, per line section |
| Government investment / large construction | none | 15 major operations (ZAC, districts, facilities) |
| Timelines and completion dates | partial | per record, with status |
| Geographic impact areas | none | coordinates + catchment-based impact model |
| Reliable sources | portal URLs only | per-record source + `seeds/README.md` provenance |
| Impact on surrounding zones / score | model existed, no data to run on | `impact_score` per record + per-IRIS `future_development_score` |

## Deliverables

1. Verified data (tracked Python, exported to GeoJSON):
   - `rei/transport/projects.py` -- 46 Grand Paris Express and Tram T1 east
     stations across 75/92/93/94, official SGP/IDFM coordinates.
   - `rei/development/projects.py` -- 15 major ZAC, new districts and public
     facilities.
   - `seeds/build_projects.py` exports both to `seeds/*.geojson`.
2. Ingestion (registry `runnable`):
   - `transport_projects` (`ProjectCollector`) and `development_projects`
     (`DevelopmentProjectsCollector`) load the verified seed by default, or a
     GeoJSON/CSV path to override (e.g. GPU/ZAC perimeters).
   - Schema: descriptive + score columns added to `gis.transport_projects`; new
     `gis.development_projects` table.
3. Scoring: `rei/scoring/future_development.py` aggregates both layers into a
   per-IRIS `future_development_score` (0-100), file-storage friendly.
4. This report and `seeds/README.md` (provenance and refresh instructions).

## The dataset

Each record carries the fields the brief asked for: project name, type,
description, status, expected completion, coordinates, official source, and an
impact estimate (`impact_score`, 0-100). Full per-record geometry is in the
seed/GeoJSON; the tables below summarise.

### Transport (46 stations)

Coordinates are the official Societe des Grands Projets positions (via IDFM open
data). Status and opening dates are the June-2026 view; Grand Paris Express dates
have slipped repeatedly, so treat them as best-estimate and refresh before any
decision.

| Section | In-scope stations | Status | Opening | Impact (0-100) |
|---|---:|---|---|---|
| GPE L15 South (Pont de Sevres - Noisy-Champs) | 16 | testing | Apr 2027 | 89-100 |
| GPE L16 (Pleyel - Noisy-Champs, 1st sections) | 7 | under construction | 2027-2028 | 86-100 |
| GPE L17 (Pleyel - Le Bourget) | 1 in-scope (+ shared) | under construction | 2027-2028 | ~86 |
| GPE Saint-Denis Pleyel super-hub | 1 | under construction | 2027 | 100 |
| GPE L15 West (Pont de Sevres - Pleyel) | 9 | under construction | ~2030 | 56-68 |
| GPE L15 East (Pleyel - Champigny) | 10 | under construction | ~2031 | 44-56 |
| Tram T1 east (Bobigny - Val de Fontenay) | 2 | building / planned | 2026 / 2029 | 43-56 |

Highest individual catalysts (near-term hubs): Saint-Denis Pleyel (100), Villejuif
Institut Gustave Roussy, Noisy-Champs, Le Bourget RER (L16/L17), La Defense
(L15 West), Val de Fontenay and Rosny Bois-Perrier (L15 East). Lines 14 (Orly),
11 (Rosny) and the RER E west extension are already in service and are treated as
existing accessibility, not pipeline.

### Development: ZAC, districts, public facilities (15)

| Project | Type | Commune (dept) | Status | Completion | Impact |
|---|---|---|---|---:|---:|
| Village des Athletes (Olympic legacy) | mixed-use district | Saint-Ouen (93) | under construction | 2026 | 100.0 |
| ZAC Campus Grand Parc | mixed-use district | Villejuif (94) | under construction | 2030 | 61.9 |
| ZAC Coeur Pleyel | transport-hub district | Saint-Denis (93) | under construction | 2030 | 61.9 |
| Coeur d'Orly | business district | Paray-Vieille-Poste (94) | under construction | 2030 | 61.1 |
| ZAC Victor Hugo (eco-district) | large housing | Bagneux (92) | under construction | 2028 | 55.6 |
| Bruneseau (Paris Rive Gauche nord) | mixed-use district | Paris 13e (75) | under construction | 2030 | 50.0 |
| Clichy-Montfermeil NPNRU | urban renewal | Clichy-sous-Bois (93) | under construction | 2030 | 43.7 |
| Campus Condorcet | university | Aubervilliers (93) | under construction | 2029 | 42.9 |
| Fort d'Aubervilliers eco-district | large housing | Aubervilliers (93) | under construction | 2030 | 39.7 |
| ZAC Charenton-Bercy | mixed-use district | Charenton-le-Pont (94) | approved | 2032 | 39.4 |
| ZAC Bercy-Charenton | mixed-use district | Paris 12e (75) | planned | 2033 | 39.4 |
| Seine Gare Vitry / Les Ardoines | urban renewal | Vitry-sur-Seine (94) | under construction | 2031 | 38.4 |
| CHU Saint-Ouen Grand Paris Nord | hospital | Saint-Ouen (93) | under construction | 2031 | 38.1 |
| ZAC Ivry-Confluences | urban renewal | Ivry-sur-Seine (94) | under construction | 2032 | 37.7 |
| Parc Chapelle Charbon | park | Paris 18e (75) | under construction | 2030 | 15.9 |

Development coordinates are approximate site centroids, which is sufficient for
the catchment-based impact model. Impact scores are as of 2026 (they ramp toward
completion, so they rise each year a project is held).

## Impact methodology

Two layers, one philosophy: a project's effect on surrounding land is its peak
potential, decayed by distance and ramped by how close it is to delivery. This
reuses the existing `MODE_PROFILE` in `rei/transport/impact.py` so the data layer
and the parcel model agree.

Per-project `impact_score` (0-100):
- Transport (`project_impact_score`): peak uplift by mode (metro 0.18, tram 0.10,
  RER 0.15, ...) times a ramp that is 40% at announcement and full by opening,
  normalised so a metro at full ramp scores ~100, plus a hub bonus (8 for an
  interchange, 12 for a major hub, 15 for the Pleyel super-hub).
- Development (`dev_impact_score`): peak uplift by type (business district 0.14,
  transport-hub district 0.13, mixed-use 0.12, urban renewal 0.11, large housing
  0.10, hospital 0.10, university 0.09, cultural 0.06, park 0.05) times the same
  ramp, times a programme-size factor (~0.8-1.3).

Per-IRIS `future_development_score` (0-100, `rei/scoring/future_development.py`):
for each IRIS, take the strongest distance-decayed catalyst in catchment (metro
1,500 m, tram 1,000 m, development 1,500 m), plus 0.15 times the sum of the
remaining catalysts (a mild agglomeration bonus), capped at 100. A zone with no
catalyst in catchment scores 0, which is the correct null.

## How to refresh

```bash
python -m rei.cli ingest transport_projects     # verified seed -> gis.transport_projects (or data/geo/)
python -m rei.cli ingest development_projects    # verified seed -> gis.development_projects
python seeds/build_projects.py                   # re-export the GeoJSON deliverables
```

Live sources for ongoing refresh (see `seeds/README.md` for full URLs):
- Transport: Societe des Grands Projets; IDFM open data (`projets_lignes_idf`,
  `projets_arrets_idf`, GPE station points).
- Rezoning / operations: API Carto GPU (`zone-urba`, `prescription-surf` for ZAC),
  already wired in `rei/ingestion/gpu.py` (`GpuCollector`, `ZacCollector`,
  `ScotCollector`); flip those registry tiers as coverage is validated.
- Master plans: SDRIF-E and SCoT (regional/intercommunal), and council minutes /
  public enquiries via the planning-document agent (`rei/ai_agent/`).

## Integration into scoring (recommended, low-risk)

The methodology review (`RANKING_METHODOLOGY_REVIEW.md`) is explicit that the
composite is delicate and that a single strong factor must not promote a
structurally weak zone. So the recommendation is additive and gated, not a
reweighting:

1. Surface first. Publish `future_development_score` as its own column and map
   layer. The data is already consumed by `rei/zoning/detectors.py`
   (`_transport_commitment` now returns real counts), so the density-change
   signal comes alive with no scoring change.
2. Feed Appreciation, not Value. Future development is an appreciation catalyst.
   Blend it into the Appreciation sub-score at a modest weight (suggest 10-15%)
   so it supports growth, where it belongs, rather than the mispricing/Value term.
3. Keep the gates. Apply it after the existing quality gates and value-trap
   haircut. A planned metro does not cancel weak rental demand or thin liquidity;
   it should lift a sound-but-overlooked zone, not rescue a trap. Concretely:
   `appreciation_adj = clip(appreciation + w * future_development_score, 0, 100)`
   with `w` ~0.12, applied before the gates in `rei/scoring/institutional.py`.
4. Show the horizon. A 2031 catalyst is not a 2027 one; the ramp already encodes
   this. Display the dominant project and its date in the IRIS detail panel so the
   signal is auditable.

This answers the brief's core case directly: a cheap zone on a 2027 GPE hub now
carries a high `future_development_score`, lifting its appreciation outlook, while
the trap gates still protect against cheap-for-a-reason zones with no catalyst.

## Limitations and next steps

- Coverage is the Grand Paris core and the largest projects; it is a high-value
  starter set, not a census. Extend via the GPU/ZAC collectors and the document
  agent.
- Grand Paris Express dates are volatile; refresh from SGP before decisions.
- Development perimeters are point centroids; replacing them with ZAC polygons
  from API Carto GPU would let the impact model use true affected areas instead of
  fixed catchments.
- Multi-year INSEE population/income (already on the roadmap) plus this layer would
  let Appreciation combine realised momentum with forward catalysts, which is the
  intended end state.
