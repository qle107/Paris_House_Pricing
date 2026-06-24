# Project seeds: Grand Paris core future-development intelligence

Verified, source-checked seeds of forward-looking projects (next ~5-10 years) for
the Grand Paris core (Paris 75 + Hauts-de-Seine 92 + Seine-Saint-Denis 93 +
Val-de-Marne 94), feeding the zone-evaluation model with forward-looking
indicators.

## Files

- Canonical data (tracked, Python):
  - `rei/transport/projects.py` -- Grand Paris Express + Tram T1 east stations.
  - `rei/development/projects.py` -- ZAC / districts / public facilities.
- Portable export (git-ignored, regenerated): `transport_projects.geojson`,
  `development_projects.geojson`. Rebuild with:

  ```bash
  python seeds/build_projects.py
  ```

## How it enters the model

```bash
python -m rei.cli ingest transport_projects     # -> gis.transport_projects (or data/geo/)
python -m rei.cli ingest development_projects    # -> gis.development_projects (or data/geo/)
```

Both collectors load the verified seed by default; pass a GeoJSON/CSV path to
override (e.g. ZAC perimeters exported from API Carto GPU). Each record carries an
`impact_score` (0-100); `rei/scoring/future_development.py` aggregates both layers
into a per-IRIS `future_development_score`.

## Provenance

Station coordinates are the official Societe des Grands Projets (SGP) positions
republished by Ile-de-France Mobilites open data ("Point de localisation des
gares du Grand Paris Express", RGF93). Status and opening dates are the June 2026
view and were cross-checked against the sources below. Development-project
coordinates are approximate site centroids (sufficient for the catchment-based
impact model).

### Transport
- Societe des Grands Projets (Grand Paris Express): https://www.societedesgrandsprojets.fr/
- IDFM open data, GPE station locations: https://data.iledefrance-mobilites.fr/explore/dataset/point-de-localisation-des-gares-du-grand-paris-express/
- IDFM open data, projected lines/stops: datasets `projets_lignes_idf`, `projets_arrets_idf`
- Line status / opening dates (June 2026): Grand Paris Express schedule reporting
  (Sortiraparis, Wikipedia "Grand Paris Express"). L15 South ~Apr 2027; L16/L17
  first sections ~Q2 2027; L15 West ~2030; L15 East ~2031; Tram T1 east phase 1
  ~2026, phase 2 (Val de Fontenay) ~2029.

### Development (ZAC / districts / facilities)
- Plaine Commune (Pleyel, Campus CHU, Fort d'Aubervilliers): https://plainecommune.fr/projets/grands-projets-urbains/
- Ville de Villejuif / EPA ORSA (Campus Grand Parc, Ardoines): https://www.villejuif.fr/ ; https://www.epa-orsa.fr/
- AP-HP / EPAURIF (CHU Saint-Ouen Grand Paris Nord): https://www.aphp.fr/ ; https://www.epaurif.fr/
- Grand Paris Amenagement (Charenton-Bercy, Coeur d'Orly, Fort d'Aubervilliers): https://www.grandparisamenagement.fr/
- SEMAPA / Ville de Paris (Bercy-Charenton, Bruneseau, Chapelle Charbon): https://www.semapa.fr/ ; https://www.paris.fr/
- Grand-Orly Seine Bievre / SADEV94 (Ivry-Confluences): https://www.grandorlyseinebievre.fr/
- ANRU (Clichy-Montfermeil NPNRU): https://www.anru.fr/

## Caveats

- Opening dates for the Grand Paris Express have slipped repeatedly; treat them as
  the best June-2026 estimate and refresh from SGP before any decision.
- The development list is a curated starter set, not exhaustive. Extend it with the
  GPU/ZAC perimeter collector (`rei.ingestion.gpu.ZacCollector`) and the
  planning-document agent (`rei/ai_agent/`).
