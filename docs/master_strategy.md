# France RE intelligence: master strategy

Strategy and data inventory for the `real-estate-intelligence` repository. Source list: `config/sources.yaml`.

> Open data only for feeds (INSEE, DVF, Cadastre, BAN, Sit@del, GPU, etc.). SIRENE live API needs a free INSEE key. LLM extraction: manual, Ollama, or OpenAI.

## Contents

1. Analytical lenses
2. Data sources
3. City scoring model
4. Zoning / density signals
5. Municipal documents
6. Transport impact
7. Land acquisition patterns
8. Platform architecture
9. AI research agent
10. Due-diligence checklist
11. Worked examples

---

# Part 1: analytical lenses

Location value follows demand vs supply. Ten lenses, each with leading and lagging indicators:

**1. Demographics:** population level matters less than growth and age mix. Leading: migration, household size. Lagging: census counts, vacancy.

**2. Employment:** jobs set affordability. Leading: FDI, business creation (SIRENE). Lagging: unemployment.

**3. Migration:** inflows tighten supply before prices adjust. Leading: INSEE mobility flows. Lagging: population change.

**4. Infrastructure:** public investment capitalises into land. Leading: budgets, ZAC creation. Lagging: completed-project premia.

**5. Transport:** fixed rail access affects values within ~800 m–2 km. Leading: DUP, opening dates. Lagging: ridership, post-opening comps. (Part 6.)

**6. Housing supply:** demand becomes rent growth where supply is inelastic. Leading: permits/capita (Sit@del). Lagging: completions.

**7. Zoning:** buildable rights set land option value. Leading: PLU revision, OAP. Lagging: approved PLU, permits under new rules. (Parts 4–5.)

**8. Politics:** mayoral stance on growth affects approvals. Leading: election platforms, council votes. Lagging: permit issuance.

**9. Economic development:** anchors (universities, hospitals, clusters) support long-run demand. Leading: announced programmes. Lagging: employment catch-up.

**10. Liquidity:** transaction depth affects exit risk. Leading: sales volume trend. Lagging: time-on-market.

Lenses 1–5 and 9 → demand; 6–8 → supply and option value; 10 → exit risk. Part 3 scores communes; Parts 4–6 add zoning and transport signals.

---

# Part 2: France data sources (inventory)

From `config/sources.yaml`. `tier=runnable` = working collector; `scaffold` = stub to finish.


### Demographics & socio-economics

| Dataset | Access | Free | Cadence | Granularity | Key variables | Score |
|---|---|---|---|---|---|:--:|
| **INSEE - Population legale & recensement (RP)** | `api.insee.fr/melodi/V2` | Yes | annual | IRIS | population, age, sex, csp | 10/10 |
| **INSEE - Emploi / population active (RP + estimations d'emploi)** | `api.insee.fr/melodi/V2` | Yes | annual | commune | actifs, emploi, chomage, secteur_activite | 9/10 |
| **INSEE FiLoSoFi - revenus disponibles & pauvrete** | `api.insee.fr/melodi/V2` | Yes | annual | IRIS | revenu_median, taux_pauvrete, deciles, gini | 9/10 |
| **INSEE - Migrations residentielles (mobilite residentielle)** | `api.insee.fr/melodi/V2` | Yes | annual | commune | entrants, sortants, solde_migratoire, origine | 8/10 |
| **INSEE - Menages & projections (Omphale)** | `api.insee.fr/melodi/V2` | Yes | annual | commune | nb_menages, taille_menage, projection_menages | 8/10 |

### Business & economy

| Dataset | Access | Free | Cadence | Granularity | Key variables | Score |
|---|---|---|---|---|---|:--:|
| **INSEE SIRENE - etablissements & creations d'entreprises** | `api.insee.fr/api-sirene/3.11` | Yes (free key) | daily | address | siret, naf, effectif, date_creation | 8/10 |
| **INSEE BPE - Base Permanente des Equipements (commerces, services)** | `api.insee.fr/melodi/V2` | Yes | annual | commune | commerces, sante, education, sport | 7/10 |
| **Business France - investissements etrangers (FDI/IDE)** | `www.businessfrance.fr/bilan` | Yes | annual | region | projets, emplois, secteur, pays_origine | 6/10 |

### Property market

| Dataset | Access | Free | Cadence | Granularity | Key variables | Score |
|---|---|---|---|---|---|:--:|
| **DGFiP DVF - Demandes de Valeurs Foncieres (geolocalisees)** | `api.cquest.org/dvf` | Yes | biannual | parcel | valeur_fonciere, surface_bati, type_local, date_mutation | 10/10 |
| **Cerema DV3F / DVF+ agregee a la mutation** | `www.data.gouv.fr/datasets/demande-de-valeu…` | Yes | biannual | parcel | segment_marche, prix_m2, filtre_qualite | 8/10 |
| **Observatoires Locaux des Loyers (OLL) + carte des loyers ANIL** | `www.data.gouv.fr/datasets/carte-des-loyers…` | Yes | annual | commune | loyer_m2_maison, loyer_m2_appartement, loyer_m2_t3 | 8/10 |

### Construction & permits

| Dataset | Access | Free | Cadence | Granularity | Key variables | Score |
|---|---|---|---|---|---|:--:|
| **SDES Sit@del - permis de construire & autorisations d'urbanisme** | `www.data.gouv.fr/datasets/base-des-permis-…` | Yes | monthly | commune | type_permis, nb_logements, surface, date_autorisation | 10/10 |
| **SDES - logements autorises & commences (series mensuelles)** | `www.data.gouv.fr/datasets/logements-autori…` | Yes | monthly | departement | autorises, commences, surface | 8/10 |

### Land, cadastre & zoning

| Dataset | Access | Free | Cadence | Granularity | Key variables | Score |
|---|---|---|---|---|---|:--:|
| **Etalab - Plan Cadastral Informatise (PCI) vecteur** | `cadastre.data.gouv.fr/data/etalab-cadastre…` | Yes | quarterly | parcel | geometry, contenance, section, numero | 10/10 |
| **Base Adresse Nationale (BAN) + geocodage** | `api-adresse.data.gouv.fr` | Yes | continuous | address | lat, lon, label, citycode | 9/10 |
| **Geoportail de l'Urbanisme (GPU) - PLU/PLUi/POS zonage + prescriptions** | `apicarto.ign.fr/api/gpu` | Yes | continuous | parcel | libelle, typezone, destdomi, partition | 10/10 |
| **SCoT - Schemas de Coherence Territoriale (via GPU)** | `apicarto.ign.fr/api/gpu` | Yes | continuous | epci | perimetre, orientations, document_pdf | 7/10 |
| **ZAC / operations d'amenagement (open data local + GPU prescriptions)** | `apicarto.ign.fr/api/gpu` | Yes | irregular | parcel | perimetre_zac, amenageur, programme | 8/10 |

### Transport

| Dataset | Access | Free | Cadence | Granularity | Key variables | Score |
|---|---|---|---|---|---|:--:|
| **Point d'Acces National (transport.data.gouv.fr) - GTFS / GTFS-RT** | `transport.data.gouv.fr/api/datasets` | Yes | continuous | stop | stops, routes, frequencies, modes | 9/10 |
| **Grands projets de transport (SGP/GPE, SNCF Reseau, regions)** | `www.societedugrandparis.fr/` | Yes | irregular | station | ligne, station, mise_en_service, statut | 9/10 |

### Risk & environment

| Dataset | Access | Free | Cadence | Granularity | Key variables | Score |
|---|---|---|---|---|---|:--:|
| **Georisques (BRGM) - inondation, retrait-gonflement argiles, PPRN** | `georisques.gouv.fr/api/v1` | Yes | continuous | parcel | azi, ppr, tri, argiles | 8/10 |
| **ADEME - DPE logements (observatoire performance energetique)** | `data.ademe.fr/data-fair/api/v1/datasets` | Yes | continuous | address | classe_dpe, conso_energie, ges, surface | 7/10 |

### Public services & social

| Dataset | Access | Free | Cadence | Granularity | Key variables | Score |
|---|---|---|---|---|---|:--:|
| **MEN - annuaire etablissements + IPS (indice position sociale)** | `data.education.gouv.fr/api/explore/v2.1` | Yes | annual | address | ips, effectifs, type_etab, resultats_brevet | 7/10 |
| **SSMSI - bases communales de la delinquance enregistree** | `www.data.gouv.fr/datasets/bases-statistiqu…` | Yes | annual | commune | type_infraction, nombre, taux_pour_mille | 6/10 |

### Public finance & governance

| Dataset | Access | Free | Cadence | Granularity | Key variables | Score |
|---|---|---|---|---|---|:--:|
| **OFGL / DGFiP - comptes & budgets des collectivites locales** | `data.ofgl.fr/api/explore/v2.1` | Yes | annual | commune | recettes, depenses, investissement, encours_dette | 7/10 |
| **Deliberations de conseils municipaux / comptes-rendus (sites mairie)** | `—` | Yes | irregular | commune | date_seance, ordre_du_jour, deliberations_pdf | 9/10 |
| **Concertations & enquetes publiques (registres en ligne, prefectures)** | `—` | Yes | irregular | commune | objet, periode, documents, avis_commissaire | 8/10 |
| **SRADDET / SDRIF / plans de developpement regionaux** | `—` | Yes | irregular | region | objectifs_logement, armature_urbaine, corridors | 7/10 |

**Usefulness score (1–10):** forecast value, granularity, update frequency. Core spine: DVF, Cadastre, INSEE population, GPU, Sit@del.

---

# Part 3: city scoring model

The model converts the Part 1 lenses into a single **City Attractiveness Score, 0–100**, computed for every commune (and, where data allows, arrondissement and IRIS). It is implemented in `rei/scoring/` (`engine.py`, `indicators.py`, `weights.yaml`).

### Method

1. **Assemble features** per commune from the warehouse (`scores.mv_commune_features`): population CAGR, median income, supply tightness, rent level, price CAGR, transaction depth, transport-stop access, buildable upside, density-change score, hazard count.
2. **Normalise each component to 0–100 by percentile rank** across the scored universe. Percentile rank (not absolute thresholds) is used because it is cycle- and metro-robust: "85th percentile of price momentum" stays meaningful as markets move. Missing data maps to a neutral 50 (never punitive). Direction `-1` inverts indicators where lower is better.
3. **Weight and sum** using a profile (weights sum to 1.0).
4. **Apply a risk overlay** multiplicatively (0.7–1.0): heavy flood/clay exposure caps the score regardless of opportunity.

### Components, weights and rationale

Two profiles ship; pick per strategy. (From `rei/scoring/weights.yaml`.)

| Component | Core-plus | Value-add/opp. | Leading? | Source feature |
|---|:--:|:--:|:--:|---|
| Population growth | 0.10 | 0.08 | leading | `pop_cagr` |
| Income growth | 0.10 | 0.07 | mixed | `revenu_median` |
| Employment growth | 0.10 | 0.10 | leading | `emp_proxy` |
| Business growth | 0.05 | 0.07 | leading | `biz_proxy` (SIRENE net openings) |
| Infrastructure/transport | 0.10 | 0.15 | leading | `transport_score` |
| Housing-supply constraint | 0.15 | 0.10 | leading | `tightness` |
| Rental growth | 0.10 | 0.08 | mixed | `loyer_m2` |
| Price growth | 0.10 | 0.05 | lagging | `price_cagr_5y` |
| Liquidity | 0.08 | 0.05 | lagging | `n_sales_total` |
| Development potential | 0.07 | 0.13 | leading | `buildable_upside` |
| Future zoning upside | 0.05 | 0.12 | leading | `density_change_score` (Part 4) |

The value-add profile weights transport, buildable upside, and zoning signals above trailing price momentum.

### Formulas

Component score (percentile transform):

```
comp_i = 100 × rank_pct(value_i ; ascending = (direction_i > 0))
```

Composite, then risk overlay:

```
raw_score   = Σ_i  weight_i × comp_i
risk_mult   = 1 − min(n_risques / 6, 1) × (1 − 0.7)          # ∈ [0.7, 1.0]
SCORE       = round( raw_score × risk_mult , 1 )             # 0–100
```

Supply tightness (derived feature):

```
tightness = (pop_cagr + price_cagr_5y) / permits_per_1000
```

High demand growth *per unit of new supply* = pricing power. `database/queries/supply_constraint.sql` ranks the universe on exactly this.

### Interpretation thresholds

| Score | Reading | Typical action |
|---|---|---|
| 80–100 | Strong demand/supply + option value | Priority market |
| 65–79 | Above average | Active pipeline |
| 50–64 | Average | Selective, asset-specific only |
| 35–49 | Weak | Avoid unless special situation |
| 0–34 | Structurally challenged | Pass |

**Caveat:** the score ranks *attractiveness of the location's trajectory*, not entry price. A high score at a rich cap rate can be a worse trade than a 65 at a dislocated price. Always pair the score with the entry-yield and the ML forward-return forecast (`rei/ml/predict.py`).

---

# Part 4: zoning and density signals

Reclassification (e.g. AU→U) or height/COS changes can move land values before comps reflect it. Signal is slow because it sits in municipal documents.

### Mechanism (France)

1. **The PLU/PLUi is the instrument:** the *Plan Local d'Urbanisme* (communal) or *intercommunal* (PLUi) fixes zones (U urban, AU to-urbanise, A agricultural, N natural) and, per zone, the rules that set buildable rights (heights, emprise/COS, setbacks, mix). Density rises when these are revised.
2. **Who decides:** the mayor and municipal (or EPCI) council initiate and approve. The state (DDT), région (SRADDET/SDRIF) and SCoT set a hierarchy the PLU must comply with, so regional housing targets *push down* into local density.
3. **The revision pathway** (each step is a public, datable signal):
   `délibération de prescription` (launch) → `PADD` debate (the political vision) → drafting of zoning + `OAP` (orientations d'aménagement) → `arrêt du projet` → `consultation/enquête publique` → `commissaire-enquêteur` report → `approbation`. Elapsed time is typically 3–6 years for a full PLU, 12–24 months for a `modification`/`déclaration de projet`.
4. **What forces it:** housing shortage + SRU social-housing penalties + a transport project + a pro-growth majority + developer pressure. When several coincide, density change is near-certain; the only question is timing.

### Density-change score

Five signals blended into 0–100 `density_change_score` (`rei/zoning/detectors.py`):

| # | Signal | What we measure | Signal strength | Horizon | Reliability | Source |
|---|---|---|:--:|:--:|:--:|---|
| s1 | **Zoning reclassification** | m² moved A/N→AU, AU→U between PLU snapshots | Very high | 0–2 yr | 0.95 | GPU diff (`plu_diff.py`) |
| s2 | **Permit acceleration** | last-12m vs prior-12m authorised dwellings | High | 0–1 yr | 0.85 | Sit@del |
| s3 | **Transport commitment** | committed station/line nodes within 1 km | Medium-high | 2–8 yr | 0.80 | GPE/SNCF pipeline |
| s4 | **Document density mentions** | count of density/rezoning facts extracted from PLU, minutes, consultations | Medium | 1–5 yr | 0.55 | AI agent (Part 9) |
| s5 | **Housing-target pressure** | extracted SCoT/SRADDET/PLH housing objectives | Medium | 2–6 yr | 0.65 | AI agent |

Weights: s1 0.35, s2 0.20, s3 0.20, s4 0.10, s5 0.15. Hard, already-happening signals (an actual reclassification, accelerating permits) dominate soft ones (a mention in a speech).

### How to read it

- **Score > 70, s1/s2 high:** reclassification or permit surge underway.
- **Score 40–70, s3–s5:** transport/planning signals on a 3–6 year horizon.
- **Score < 40:** no near-term catalyst.

The platform recomputes this each time GPU zoning, permits, or the document corpus refresh, and raises an alert (Part 9) when a commune crosses threshold or a new s1/s2 event lands.

---

# Part 5: municipal document intelligence

Document types the AI agent extracts (`rei/ai_agent/prompts.py`):

**PLU / PLUi.** *Where:* Géoportail de l'Urbanisme (GPU) for the zoning vector + the full document set (rapport de présentation, PADD, règlement, OAP, annexes); commune/EPCI websites for revisions in progress. *Sections that matter:* the **PADD** (political vision: densification corridors, where growth is steered), the **règlement** per zone (heights, emprise au sol, COS where retained, stationnement), the **OAP** (sector-specific programmes, often the clearest pre-development signal), the zoning plan itself. *Keywords:* `densification, intensification, hauteur, gabarit, emprise au sol, COS, ouverture à l'urbanisation, zone AU, secteur de projet, OAP, mixité`. *Indicators of future density:* new/expanded AU zones, raised heights, reduced parking minimums, OAP sectors over transport nodes, suppression of COS caps.

**SCoT.** *Where:* GPU + the syndicat mixte/EPCI site. *Sections:* the **DOO** (document d'orientation et d'objectifs, binding), armature urbaine (which towns absorb growth), housing production targets, density floors near transit. *Keywords:* `armature urbaine, polarités, objectifs de production de logements, densité minimale, TOD`. *Indicators:* a commune named a growth pole; minimum-density rules near stations; greenfield-limiting "ZAN" (zéro artificialisation nette) pushing density into existing fabric.

**Municipal council minutes (délibérations / comptes-rendus).** *Where:* mairie website "conseil municipal" pages (PDFs); legally must be published. *Sections:* agenda items on PLU revision, ZAC creation, land acquisition/preemption (DPU), public-land disposals, partnerships with aménageurs/bailleurs. *Keywords:* `révision du PLU, modification, ZAC, concession d'aménagement, cession de terrain, droit de préemption, ZAD, convention`. *Indicators:* prescription of a PLU revision; ZAC dossier de création/réalisation; land bought or preempted by the commune/EPF; developer consultation launched.

**Urban-planning committee / commission reports.** *Where:* EPCI and métropole sites; ZAC review committees. *Sections:* programme, phasing, dwelling counts, public-equipment plans. *Indicators:* dwelling-count targets, phasing dates, infrastructure commitments.

**Public consultations / enquêtes publiques.** *Where:* dedicated registres (often `registre-numerique.fr`, `jecoteliris…`), préfecture sites, GPU. *Sections:* objet of the operation, perimeter, the commissaire-enquêteur's *avis* and reservations. *Indicators:* a named perimeter (geolocatable land), a favourable avis (de-risks approval), reservations that may delay.

**Mayor speeches / municipal strategic plans / press.** *Where:* commune site, local press, municipal magazine. *Indicators:* stated ambitions ("X new homes by 20YY", "éco-quartier", "renouvellement urbain"), naming of specific sectors. Lower reliability; treat as `s4`, corroborate with hard documents.

**Regional development plans (SRADDET / SDRIF-E).** *Where:* région/Île-de-France `iledefrance.fr`, GPU. *Sections:* housing objectives by territory, transport priorities, density and ZAN rules. *Indicators:* per-territory housing quotas pushed down to local PLUs; corridors prioritised for intensification.

**Infrastructure plans (SGP/GPE, SNCF Réseau, region).** *Where:* `societedugrandparis.fr`, regional mobility authorities, transport.data.gouv.fr. *Indicators:* confirmed opening dates, station-area development perimeters, contrats de développement territorial (CDT).

## Checklist: 100+ indicators of future density / redevelopment

Score a commune/sector: each YES is a positive signal; clusters across themes A–H carry more weight. (The agent emits these as structured facts; analysts confirm.)

**A. Zoning & PLU (1–18)**
1. PLU/PLUi revision prescribed (délibération). 2. Modification/déclaration de projet underway. 3. New AU (à urbaniser) zone created. 4. AU→U reclassification. 5. A or N land reclassified to AU/U. 6. Maximum height raised in a zone. 7. Emprise au sol coefficient raised. 8. COS cap removed or raised (where retained). 9. Parking minimums reduced/removed. 10. New OAP sector defined. 11. OAP located over/near a transit node. 12. Mixité-sociale obligations added (signals new programmes). 13. "Secteur de projet" or "périmètre d'attente" delimited. 14. Emplacements réservés for housing/equipment added. 15. Change-of-use enabled (office→resi, industrial→mixed). 16. Densité minimale imposed near stations. 17. ZAN-driven intensification of existing fabric. 18. PADD explicitly targets densification corridors.

**B. Permits & construction (19–30)**
19. Authorised-dwelling 12m count accelerating vs prior year. 20. Large (>50-unit) permit issued. 21. Cluster of permits in one IRIS. 22. Non-residential permit (office/lab/logistics), a jobs signal. 23. Demolition permits (site assembly). 24. Permits on former industrial parcels. 25. Rising share of collective (vs individual) housing. 26. Permit pipeline > regional average per capita. 27. VEFA (off-plan) programmes launched by national developers. 28. Social-housing (bailleur) programmes permitted. 29. Building-height of new permits trending up. 30. Permits adjacent to a planned station.

**C. Land & cadastre (31–42)**
31. Large underused parcels (low emprise) in U/AU zones. 32. Public/municipal land identified for disposal. 33. EPF (établissement public foncier) acquisition in commune. 34. Commune exercising droit de préemption (DPU). 35. ZAD (deferred-development zone) created. 36. Surface parking lots in central/transit locations. 37. Single-storey retail/big-box on large plots near transit. 38. Brownfield/friches inventoried (Cartofriches). 39. Fragmented ownership being assembled. 40. Religious/institutional landholdings coming to market. 41. Rail/port/utility land released. 42. Agricultural land inside the urban envelope.

**D. Transport (43–54)**
43. New metro/RER/tram/BRT line declared (DUP). 44. Station location confirmed within commune. 45. Funding secured / works contract signed. 46. Tunnelling or construction visibly underway. 47. Confirmed opening date within 8 years. 48. Station-area development perimeter (CDT/ZAC) defined. 49. Existing line frequency/capacity upgrade. 50. New interchange (hub) effect. 51. Bus network restructured around a node. 52. Cycle-network/RER-Vélo investment. 53. Park-and-ride or mobility hub planned. 54. Road/bridge improving access to a development sector.

**E. Economic development (55–66)**
55. University campus creation/expansion. 56. Hospital/CHU expansion or relocation. 57. Research lab / grand équipement (e.g., cluster) announced. 58. Corporate HQ relocation/large pre-let. 59. FDI project landed in the territory. 60. Pôle de compétitivité / cluster funding. 61. Logistics/data-centre investment (jobs + land use). 62. Cultural/sport anchor (museum, stadium, Olympic legacy). 63. Tech/start-up incubator established. 64. Large public-sector employer arriving. 65. Tourism/leisure investment. 66. Special economic/innovation zone designation.

**F. Political & fiscal (67–78)**
67. Pro-development municipal majority (election platform). 68. Mayor public statements favouring growth/housing. 69. SRU social-housing deficit + penalties (forces production). 70. Municipal fiscal pressure (incentive to grow tax base). 71. Strong investment capacity (OFGL: épargne brute, low debt). 72. PLH (programme local de l'habitat) with high targets. 73. Contrat with state/region tying funding to housing. 74. EPCI taking planning competence (PLUi). 75. Public-land company (SPL/SEM) created for projects. 76. Political stability (low turnover) reduces execution risk. 77. Opposition to growth (NIMBY), a negative flag. 78. Referendum/consultation outcomes on projects.

**G. Public consultations & projects (79–90)**
79. Concertation préalable launched (named perimeter). 80. Enquête publique open. 81. Favourable commissaire-enquêteur avis. 82. ZAC dossier de création approved. 83. ZAC dossier de réalisation approved. 84. Concession d'aménagement awarded to a developer. 85. Éco-quartier label/process. 86. NPNRU (renouvellement urbain) programme. 87. Appel à projets urbains innovants (e.g., "Inventons…"). 88. Master-developer (aménageur) appointed. 89. Public-equipment programme (schools) signalling new population. 90. Phasing calendar published.

**H. Demand & market corroboration (91–104)**
91. Net in-migration of 25–39 cohort. 92. Household-size decline. 93. School-enrolment rising. 94. Rents accelerating vs metro. 95. Transaction volume rising (liquidity). 96. New-build absorption fast (low unsold stock). 97. Price/m² gap vs adjacent better-served commune (catch-up potential). 98. Falling crime (gentrification turn). 99. School-quality (IPS) rising. 100. DPE-poor stock share (value-add renovation pool). 101. Vacancy falling. 102. Commercial vacancy falling on high street. 103. Café/retail openings (SIRENE), amenity momentum. 104. Search/rental-listing demand indices rising.

A sector lighting up across **A+C+D** (rezoning + assemblable land + committed transport) is the textbook pre-repricing setup of Part 7.

---

# Part 6: transport analysis

New fixed-rail access is the most reliable and measurable value catalyst in French residential real estate. The model (in `rei/transport/impact.py`) attributes an expected uplift to every parcel within a project's catchment, then ranks projects.

### Mode profiles (catchment, peak uplift, time-to-peak)

These are *priors*: calibrate per metro against your own DVF event studies around past openings; the ML layer then learns the realised effect.

| Mode | Primary catchment | Secondary | Peak value uplift | Years to peak |
|---|:--:|:--:|:--:|:--:|
| Metro (incl. GPE) | 800 m | 1500 m | +18% | 3 |
| RER | 1000 m | 2000 m | +15% | 3 |
| Train (TER/Transilien) | 1200 m | 2500 m | +10% | 4 |
| Tram | 500 m | 1000 m | +10% | 2 |
| BRT | 400 m | 800 m | +6% | 2 |
| Bus (high-freq) | 300 m | 600 m | +3% | 1 |

### How investors analyze a project

- **Expected impact radius:** primary catchment captures the full premium; it decays linearly to zero at the secondary boundary (10-min vs 20-min walk).
- **Timeline:** premium is *not* a step at opening. ~40% capitalises at credible announcement/DUP, ramping to peak ~2–4 years post-opening as service reliability is proven. Most uplift is priced in between announcement and opening.
- **Impact on rents vs values:** values move first and more (option + owner-occupier demand); rents follow with the new resident mix. Yields compress in the catchment as the area de-risks.
- **Formula** (`expected_uplift`):
```
uplift = peak × distance_decay × time_ramp
distance_decay = 1                      if dist ≤ primary
               = 1 − (dist−primary)/(secondary−primary)   within secondary
               = 0                       beyond secondary
time_ramp = clamp(1 − years_to_open/(years_to_peak+6), 0.4, 1.0)
```

### Ranking system

Projects are ranked (`rank_projects()`) by **catchment scale × peak uplift × imminence**:

```
project_score = parcels_within_800m × peak_uplift_mode
```

extended in practice by `× catchment_population × (1 / years_to_open)`. GPE adds ~68 stations (lines 15/16/17/18 plus 14/11 extensions) through 2026–2031; Part 11 examples focus on inner-belt communes around new stations.

### Transit-oriented development (TOD) screen

Parcels that are (a) inside an 800 m GPE catchment, (b) currently low-density (low emprise/FAR), and (c) in a U/AU zone with a pro-density PLU signal are flagged as TOD targets: the intersection computed by `rei/gis/density.buildable_upside` × `rei/transport/impact.project_parcel_impact` × `rei/zoning/detectors`.

---

# Part 7: land acquisition patterns

Residual land value = (value of what can be built) − (construction + fees + developer margin). Land re-rates when buildable floor area or €/m² rises, from zoning (more/denser rights) or from accessibility and amenities. Buy before that re-rating where Parts 4–6 show it is likely.

### Target typologies

- **Underutilised land in U/AU zones:** large parcels with low emprise (single-storey, big garden, surface storage) where the PLU already (or soon will) permit far more. Highest, cleanest upside.
- **Industrial / activity land:** ripe for office/resi/mixed conversion as cities push ZAN-driven intensification; often single-owner (easier assembly).
- **Surface parking lots:** central or station-adjacent, near-zero current built value, maximal upside; frequently institutionally or municipally owned.
- **Retail sites (big-box, declining high street):** large footprints, transit-adjacent, strong rezoning candidates to mixed-use.
- **Office conversion opportunities:** structurally vacant/obsolete offices (post-hybrid-work) in resi-demand locations; value-add via change-of-use (watch the règlement and DPE).
- **Brownfield (friches):** Cartofriches-listed; remediation cost offset by public subsidy and ZAN priority.
- **Transit-oriented sites:** inside GPE/tram catchments before opening.
- **Future development corridors:** sectors named in PADD/OAP/SCoT for intensification.

### The acquisition framework (how the platform finds them)

```
candidate_land =
   gis.parcels
   ⨝ low current FAR/emprise            (rei/gis/density)
   ⨝ U or AU zone                       (gis.zoning)
   ⨝ buildable_upside_m2 high           (rei/gis/density.buildable_upside)
   ⨝ density_change_score high          (rei/zoning/detectors)   ← the catalyst
   ⨝ inside transport catchment / uplift>0  (rei/transport/impact)
   ⨝ single/few owners (assemblable)    (cadastre attributes)
   − heavy hazards                      (core.risk)
```

Rank by `buildable_upside_m2 × expected_value_per_m2 × probability_of_rezoning`. The probability term *is* the `density_change_score`. This is precisely the parcel-level join the GIS and zoning modules compute.

### Capturing the upside without development risk

- **Land options / promesses de vente** conditioned on PLU change or permit; pay a small premium for the option, exercise only if the rezoning lands.
- **Off-market assembly** of fragmented parcels ahead of an OAP.
- **Partner with the aménageur** once a ZAC concession is awarded.
- **Buy the standing income** (e.g., a let big-box or car park) at its current-use yield, holding the rezoning option for free.

The discipline: only pay for option value where the *leading* signals (Parts 4–6) say the rezoning is likely within the hold. Recompute when GPU, permits, or documents refresh; alert on threshold crossings (Part 9).

---

# Part 8: platform architecture (5 layers)

The full implementation is the `real-estate-intelligence/` repository. Architecture, by layer:

### Layer 1: raw data collection (`rei/ingestion/`, `config/sources.yaml`)
One `Collector` per source (`ingestion/base.py`, `meta.ingestion_log`). HTTP client: retries, rate limits. Runnable: INSEE, DVF, Cadastre, BAN, Sit@del, GTFS, GPU. Registry: `python -m rei.cli ingest <source_id>`.

### Layer 2: data warehouse (`database/`, `rei/etl/`)
PostgreSQL + **PostGIS** + **pgvector**. Schemas: `core` (tabular feeds), `gis` (spatial layers), `docs` (planning documents + RAG), `scores` (computed), `meta` (run log). Key design choices: DVF is **range-partitioned by mutation year** (`03_partitions.sql`) because every query filters by year and each biannual refresh can replace a whole year cheaply; GiST indexes on all geometries (`04_indexes.sql`); **materialized views** (`05_materialized_views.sql`) precompute commune features (`scores.mv_commune_features`), price trends and supply intensity. Loading is idempotent **upsert via staging table + `ON CONFLICT`** (`common/db.upsert_dataframe`), so re-runs never duplicate. High-volume national cleaning uses **Polars + DuckDB** off Parquet (`etl/dvf_transform.py`).

### Layer 3: GIS processing (`rei/gis/`)
GeoPandas/Shapely in EPSG:2154 (Lambert-93, metric). `density.py` computes footprint, CES (emprise), estimated FAR and **buildable upside** per parcel; `accessibility.py` uses PostGIS KNN (`<->`) for nearest-transit distance and catchment counts (school/employment access); `parcels.py`/`zoning.py` join parcels to dominant zoning. These produce the `development_potential` and `transport_score` features.

### Layer 4: automated intelligence (`rei/zoning/`, `rei/transport/`)
`zoning/plu_diff.py` diffs successive GPU snapshots to detect reclassifications (the `s1` signal); `zoning/detectors.py` blends the five signals into `density_change_score`; `transport/impact.py` computes parcel-level uplift and ranks projects. Alerts fire when a commune crosses threshold or a new hard signal lands.

### Layer 5: scoring + ML + AI (`rei/scoring/`, `rei/ml/`, `rei/ai_agent/`)
`scoring/engine.py` produces the 0–100 attractiveness score per commune (Part 3). `ml/` trains a **LightGBM/XGBoost** forward-price-growth model on a time-split panel (`features.py`, `train.py`) and writes `scores.ml_forecast`. The AI agent (Part 9) keeps the document-derived signals current. Orchestration: Airflow DAGs (`airflow/dags/`): daily for fast feeds, monthly check for DVF/cadastre/zoning, weekly for the AI agent, each with retries and a post-load validation task (`etl/validate.py`: pandera contracts + robust-z anomaly flags). Everything ships in Docker (`docker/`, PostGIS+pgvector image + app + dashboard + Airflow).

---

# Part 9: AI research agent

Goal: continuously turn the unstructured municipal-document universe into the structured `s1/s4/s5` signals of Part 4. Pipeline (`rei/ai_agent/`):

`crawl → download → read PDF → chunk → embed → retrieve → extract → store facts → alert`

- **Crawl** (`crawler.py`): BeautifulSoup for static mairie pages, Playwright for JS-rendered consultation registres; discovered PDFs registered in `docs.document`, then downloaded + hashed.
- **Read** (`pdf_reader.py`): pdfplumber/pypdf per page; scanned pages flagged for OCR.
- **Chunk + embed** (`rag.py`): ~500-token windows; `intfloat/multilingual-e5-base` → `docs.chunk.embedding vector(768)`.
- **Extract** (`extractors.py`, `prompts.py`): for each commune, retrieve the most relevant chunks across five French signal queries, then prompt an LLM for **strict-JSON** facts (density_increase, rezoning, housing_target, transport, redevelopment) with verbatim quote + confidence; stored in `docs.extraction`.

### LLM modes

1. **`manual` (default):** export prompt, paste JSON answer, ingest.
2. **`ollama`:** local model.
3. **`openai`:** API.

All three land identical JSON in `docs.extraction`, which feeds the density detector (s4/s5) and the alert feed (`alerts.py` → `scores.alert`, surfaced in the dashboard).

### RAG schema (`database/06_vector.sql`)
`docs.document` (one row/doc, status machine) → `docs.chunk` (text + `vector(768)` + page refs, HNSW cosine index) → `docs.extraction` (structured facts as JSONB + confidence). Chunking is page-aware so every extracted fact keeps a citable page reference.

---

# Part 10: due-diligence checklist

**Screening order:** Grand Paris inner belt, then regional metros (Bordeaux, Nantes, Rennes, Lyon, Montpellier, Toulouse), then selective Paris sectors.

**Key metrics:** committed transport with opening date, `density_change_score` (hard signals), supply tightness, buildable upside, in-migration 25–39, price gap vs better-served neighbour. Trailing price momentum is lagging.

**Common mistakes:** chasing past winners, ignoring DPE capex, treating future stations as binary, underpricing flood/clay risk.

**Early public signals:** PLU prescription, ZAC award, EPF acquisition, transport DUP, OAP perimeter.

## Checklist (200 items)

Grouped A–J (20 each). Use as an IC gating document; every "no/unknown" is a risk to price or resolve.

**A. Market & location fundamentals (1–20)**
1. Commune attractiveness score and rank. 2. Score trend over 3 prior runs. 3. Population CAGR (5/10 yr). 4. Net migration by age cohort. 5. Household-formation trend. 6. Median disposable income + trend. 7. Income distribution (deciles). 8. Employment level + growth. 9. Sector mix / employer concentration. 10. Unemployment vs national. 11. Business-creation density (SIRENE). 12. Commuting patterns / job accessibility. 13. Student population & university trajectory. 14. Tourism/seasonality exposure. 15. Adjacent-commune comparables. 16. Price/m² gap vs better-served neighbour. 17. Rent level vs metro. 18. 5-yr price and rent CAGR. 19. New-build absorption pace. 20. Demand-index / listing pressure.

**B. Supply & development pipeline (21–40)**
21. Permits per 1,000 (trailing 36m). 22. Permit trend (accelerating?). 23. Pipeline vs regional average. 24. Completions vs targets. 25. Vacancy (residential). 26. Commercial/office vacancy. 27. AU-zone stock available. 28. Land availability / scarcity. 29. ZAN constraint severity. 30. Competing schemes nearby. 31. Developer activity (who's building). 32. Social-housing pipeline (bailleurs). 33. Unsold-stock months of supply. 34. Construction-cost trend locally. 35. Labour/contractor availability. 36. Historic supply elasticity. 37. Geographic build constraints. 38. Heritage/ABF (architecte des bâtiments de France) constraints. 39. Infrastructure capacity (schools, utilities). 40. Supply tightness ratio.

**C. Zoning & entitlement (41–60)**
41. Current zone (U/AU/A/N) of the asset. 42. Règlement: height limit. 43. Emprise au sol / COS. 44. Parking requirements. 45. Use-mix permitted. 46. Setbacks/easements. 47. Emplacements réservés affecting the parcel. 48. OAP coverage. 49. PLU revision status. 50. PADD orientation for the sector. 51. Density-change score + drivers. 52. Probability/timing of favourable rezoning. 53. SCoT density rules. 54. SRADDET/SDRIF obligations. 55. PLH targets for the commune. 56. SRU social-housing quota status. 57. Prescriptions (risk, heritage) overlays. 58. Servitudes d'utilité publique. 59. Préemption (DPU/ZAD) exposure. 60. Precedent approvals nearby.

**D. Transport & infrastructure (61–80)**
61. Distance to nearest existing station. 62. Distance to committed future station. 63. Mode + expected uplift band. 64. Confirmed opening date. 65. Funding/DUP status. 66. Construction progress. 67. Service frequency/capacity. 68. Interchange/hub effect. 69. Road access & congestion. 70. Cycle infrastructure. 71. Walkability to amenities. 72. School access & quality (IPS). 73. Healthcare access. 74. Retail/services proximity (BPE). 75. Green space access. 76. Digital connectivity (fibre). 77. Utility capacity (water/power/sewer). 78. Planned infrastructure budgets (commune/EPCI). 79. CDT / station-area plan. 80. Catchment population.

**E. Asset / physical (81–100)**
81. Parcel area & shape. 82. Current built area / emprise. 83. Existing FAR vs allowed. 84. Buildable upside (m²). 85. Building age & structure. 86. DPE class distribution. 87. Renovation/capex needs. 88. Asbestos/lead/technical risk. 89. Configuration/efficiency (loss ratio). 90. Unit mix vs local demand. 91. Outdoor/parking provision. 92. Accessibility (PMR) compliance. 93. Ground conditions / geotech. 94. Soil contamination (friche). 95. Subdivision/assembly potential. 96. Title/cadastral boundaries clean. 97. Co-ownership (copropriété) status. 98. Existing leases/occupancy. 99. Conversion feasibility (office→resi). 100. Highest-and-best-use confirmed.

**F. Risk & environment (101–120)**
101. Flood zone (PPRI/AZI). 102. Clay shrink-swell (RGA). 103. Seismic zone. 104. Industrial/technological risk (PPRT). 105. Radon potential. 106. Cavities/mining. 107. Coastal erosion (if relevant). 108. Climate-transition risk (heat, water stress). 109. Noise exposure (PEB near airports). 110. Pollution/soil. 111. Insurance availability/cost. 112. Energy-regulation exposure (passoires). 113. Carbon/ESG-regulation trajectory. 114. Biodiversity/protected-species constraints. 115. Heritage protection. 116. Required mitigation cost. 117. Hazard count (risk overlay multiplier). 118. Resilience/adaptation capex. 119. Reputational/social-licence risk. 120. Force-majeure/catastrophe history.

**G. Legal & regulatory (121–140)**
121. Clean freehold/leasehold title. 122. Pre-emption rights cleared. 123. Existing permits & their validity. 124. Planning-appeal (recours) exposure. 125. Encumbrances/mortgages. 126. Servitudes/rights of way. 127. Boundary disputes. 128. Tenancy law exposure (loi de 89). 129. Rent-control (encadrement) applicability. 130. Co-ownership liabilities. 131. Tax regime (plus-value, droits de mutation). 132. VAT/TVA treatment. 133. SRU penalties pass-through. 134. Build-permit conditions/phasing. 135. Environmental authorisations. 136. Archaeology (diagnostic) risk. 137. Litigation history. 138. Counterparty/seller standing. 139. Anti-money-laundering/KYC. 140. Regulatory change pipeline.

**H. Financial & returns (141–160)**
141. Entry price vs comps (€/m²). 142. Entry yield (gross/net). 143. Reversionary potential. 144. Rent-growth assumption vs evidence. 145. Exit yield assumption + sensitivity. 146. Total dev cost (if dev). 147. Residual land value. 148. Developer margin (if dev). 149. IRR (base/bull/bear). 150. Equity multiple. 151. Cash-on-cash / income yield through hold. 152. Debt terms & LTV. 153. Interest-rate sensitivity. 154. Financing availability. 155. Liquidity / exit depth. 156. Days-on-market / bid-ask. 157. Currency (n/a EUR) & inflation linkage. 158. ML forward-return forecast. 159. Downside (capital-loss) scenario. 160. Risk-adjusted return vs hurdle.

**I. Execution & operations (161–180)**
161. Business plan clarity & milestones. 162. Local partner / aménageur quality. 163. Developer/contractor track record. 164. Permitting timeline realism. 165. Construction-cost contingency. 166. Programme phasing & cash profile. 167. Letting/sales strategy. 168. Property/asset management plan. 169. Capex schedule (DPE upgrades). 170. ESG/decarbonisation plan. 171. Tenant covenant/mix (mixed-use). 172. Community/political relations. 173. Procurement & supply chain. 174. Insurance & warranties. 175. Monitoring/reporting (data feeds). 176. Key-person/operator dependency. 177. Tax-structuring efficiency. 178. Governance & approvals. 179. Contingency/exit-flexibility. 180. Alignment of incentives (JV terms).

**J. Portfolio, ESG & strategic fit (181–200)**
181. Fit with fund mandate/profile. 182. Diversification (geography). 183. Diversification (vintage/phasing). 184. Concentration vs single catalyst (GPE line). 185. Correlation with existing assets. 186. Strategic optionality (future phases). 187. ESG/EU-taxonomy alignment. 188. Energy performance trajectory. 189. Social impact (affordable share). 190. Governance/transparency of partners. 191. Brand/reputation fit. 192. Scalability (follow-on pipeline). 193. Data/monitoring integration. 194. Hold-period vs catalyst timing. 195. Refinancing windows. 196. Exit-buyer universe identified. 197. Stress-test vs rate/recession. 198. Stress-test vs construction-cost shock. 199. Stress-test vs catalyst delay/cancellation. 200. IC sign-off & documented assumptions.

---

# Part 11: worked examples

> Indicative; refresh with live platform data.

## Five Grand Paris Express cities

Inner suburbs gaining GPE access and rezoning. Platform ranks communes and tracks catalyst timing.

### 1. Saint-Denis (93066)

- **Transport:** Pleyel GPE interchange (L14 open; L15/16/17 by 2026–27); Olympic Village → ~2,800 homes.
- **Demand:** young in-migration; large price/m² gap vs Paris 18e.
- **Supply:** ZACs (Pleyel, Confluence); EPF land assembly; high `density_change_score` (s1/s2/s3).
- **Risks:** social perception, Seine flood parcels, execution.
- **Take:** value-add/opportunistic; checklist A+C+D strong.
- **Sites:** income assets and land options within 800 m of Pleyel during the construction window.

### 2. Saint-Ouen-sur-Seine (93070)

- **Transport:** L14 (Mairie de Saint-Ouen, 2020); Docks eco-district; CHU Grand Paris Nord campus.
- **Demand:** fast price/rent re-rating in 93; deepening liquidity.
- **Supply:** former-industrial conversion largely done; remaining pipeline partly priced in.
- **Take:** high attractiveness, later cycle; core-plus over deep value-add.
- **Sites:** build-to-rent on delivered infrastructure; strict on entry price.

### 3. Villejuif (94076)

- **Transport:** GPE L14 (Orly, 2024) + L15 at Gustave Roussy; Campus Grand Parc biocluster.
- **Demand:** high-skill jobs; steady household formation.
- **Supply:** ZAC Campus Grand Parc with defined OAP; hard zoning signals.
- **Take:** lower demand risk (jobs anchor); mixed-use near station.
- **Sites:** phases with the aménageur on Campus Grand Parc.

### 4. Bagneux (92007)

- **Transport:** M4 to Lucie Aubrac (2022) + GPE L15 interchange; ZAC Victor Hugo / écoquartier.
- **Demand:** Hauts-de-Seine address at discount, now metro-linked; catch-up vs Montrouge/Châtillon.
- **Supply:** council-led densification; active pipeline.
- **Take:** value-add; A+C+D cluster.
- **Sites:** land options and conversions around the interchange.

### 5. Champigny-sur-Marne (94017)

- **Transport:** GPE L15 Sud (~2025–26) + maintenance hub (jobs); under-densified Marne frontage.
- **Demand:** historically car-dependent, cheap; re-rating mostly ahead of opening.
- **Supply:** PLU intensification around future station; `density_change_score` from s3/s4 more than s1 yet.
- **Take:** early cycle; higher timing risk.
- **Sites:** land options within 800 m of future station.

**Cycle order:** Saint-Ouen (most advanced) → Villejuif/Saint-Denis → Bagneux → Champigny (earliest).

## Bercy-Charenton (Paris 12e)

~80-ha ZAC on rail/industrial land (Porte de Bercy). RER/metro/T3 access; eastern Paris office-to-mixed shift.

- **Land:** underused rail/industrial in U/AU; high buildable upside; few owners (SNCF, City of Paris).
- **Signals:** project zoning (A), public land disposal (C), mature transit (D).
- **Risks:** recours, heritage/height, long phasing, ABF.
- **Take:** partner with aménageur on defined lots, or income around the perimeter; speculative land is hard intra-muros.
- **Sites:** delivered lots; model appeal risk (checklist G 124).

## Bordeaux Euratlantique

~738-ha OIN around Saint-Jean station. 2017 LGV (~2 h to Paris); OIN rezoned rail/industrial land for dense mixed-use.

- **Demand:** in-migration, university, tertiary jobs.
- **Supply:** OIN entitlements; large pipeline; EPA Bordeaux Euratlantique master plan.
- **Risks:** absorption pace, office oversupply, construction cost.
- **Take:** long-horizon mixed-use; stage by lot against absorption (checklist B 33, H 155).
- **Sites:** build-to-rent on delivered infrastructure.

**Contrast:** Bercy-Charenton offers intra-muros upside but is access-controlled and appeal-prone. Bordeaux Euratlantique pairs an OIN with the LGV for larger entitled density at lower entry; compare absorption and phasing before sizing exposure.

---

# Repository deliverables

1. Analytical lenses (Part 1)
2. Dataset inventory: Part 2 + `config/sources.yaml`
3. Zoning signals: Parts 4–5 + `rei/zoning/`
4. Transport model: Part 6 + `rei/transport/`
5. Scoring: Part 3 + `rei/scoring/`
6. Parcel metrics: Part 7 + `rei/gis/`
7. AI agent: Parts 8–9 + `rei/ai_agent/`
8. Checklist: Part 10
9. City examples: Part 11

Run from README: ingest, score, map, optional agent pipeline.

<!-- end of master_strategy.md -->
