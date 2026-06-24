# Institutional ranking: methodology review and recalibration

Date: 2026-06-24

Scope: analysis and a working prototype. The recommendations were later implemented in `rei/scoring/institutional.py` (see the implementation status near the end). A standalone, read-only script (`analysis/ranking_review.py`) recomputes the alternative ranking and produces the before/after figures cited here.

Universe: 5,264 IRIS across the eight Île-de-France departments. Paris has 992, the Petite Couronne (92, 93, 94) has 1,760, and the Grande Couronne (77, 78, 91, 95) has 2,512. Coverage is exactly Île-de-France, so the brief's fourth band ("rest of coverage area") is empty and is left out throughout.

## Verdict

The framework does not survive the geographic expansion. It was calibrated when every location was already expensive, liquid, and well served. Once cheap peripheral IRIS entered the universe, the most influential input, the hedonic Value score, turned into a pure inverse-price signal, because the hedonic model has no location term. The ranking now rewards cheapness and mistakes it for opportunity.

Three correlations settle it (full universe, current production scores):

| Relationship | Pearson r | Reading |
|---|---:|---|
| alpha_score vs price €/m² | -0.73 | Alpha mostly measures "how cheap is it" |
| alpha_score vs inst_value | +0.87 | Alpha is close to the discount score |
| inst_value vs price €/m² | -0.85 | "Value" is close to negative price level, not mispricing |

The consequence: of the top 200 IRIS by Alpha, 98% have Value at or above 95, 75% sit in the Grande Couronne, and the median price is €3,293/m². Every proven growth corridor (Issy-les-Moulineaux, Boulogne-Billancourt, Clichy, Saint-Ouen, Montreuil, Pantin) ranks in the bottom half of Alpha. The model ranks sleepy €2,500/m² exurbs above the strongest markets in Greater Paris.

This is not a weight-tuning problem. The Value input is mis-specified, the Rental input does not measure rent, Toxicity is computed but never used, and there are no quality gates. The fix is a recalibration of the scoring architecture, not its coefficients.

On the brief's framing: a €2,000/m² IRIS that the model "expects" at €4,000 is exactly what the current system treats as a top buy. The value-trap score below is built to separate an undervalued opportunity (cheap despite sound fundamentals) from a value trap (cheap because demand, liquidity, or growth is weak). It flags 1,194 of 5,264 IRIS (23%) as elevated-to-severe trap risk, 94 of which currently sit in the production top 20% on Alpha.

## Step 1: score distributions by zone

Mean scores by band (current production output):

| Score | Paris | Petite Couronne | Grande Couronne |
|---|---:|---:|---:|
| Attractiveness (score_total) | 54.4 | 48.3 | 49.4 |
| Institutional | 40.5 | 50.5 | 56.2 |
| Alpha | 32.8 | 49.7 | 61.4 |
| Appreciation | 42.3 | 47.0 | 55.2 |
| Rental | 59.0 | 52.2 | 44.9 |
| Value | 0.3 | 50.4 | 81.9 |
| Toxicity | 53.0 | 51.7 | 47.6 |

Supporting medians: observed price €10,265 / €5,062 / €3,249 per m²; hedonic discount -75.3% / +1.0% / +23.2%; Value 0 / 52.5 / 100.

The distributions are not comparable across bands. Value is degenerate: a median of 0 in Paris and 100 in the Grande Couronne. The hedonic model predicts roughly the same price everywhere (about €5,000/m²) because it omits location, so prime Paris reads as "overvalued, Value 0" and cheap exurbs read as "fully undervalued, Value 100." Value feeds both the Institutional composite (20%) and Alpha (about 31% after the broken transit term drops out), so both composites rise as you move outward and downmarket. That is the opposite of how an institutional screen should behave.

A second break is missingness, which is geographic and is silently mapped to a neutral 50 (`indicators.percentile_score` turns NaN into 50):

| Feature | % NaN Paris | % NaN PC | % NaN GC | Effect |
|---|---:|---:|---:|---|
| pop_cagr | 100 | 100 | 100 | demographic growth is neutral everywhere (single-year census) |
| loyer_m2 (rent) | parses to NaN for all 5,264 rows | | | the rent signal is dead (see Step 2) |
| zoning_share_au | 0 | 89 | 100 | supply and the appreciation-supply term are Paris-only |
| coverage_ratio | 1 | 80 | 100 | Development is neutral across the periphery |

Outside Paris the composite collapses onto the few inputs with peripheral coverage, the broken Value and transaction counts, which is exactly where the bias lives.

## Step 2: top-ranked IRIS audit

Top 10 by production Alpha (the Institutional top 10 is nearly identical):

| IRIS | Band | €/m² | Value | Appr | Rental | Alpha | Verdict |
|---|---|---:|---:|---:|---:|---:|---|
| République (94017) | PC | 3,926 | 100 | 79 | 89 | 88 | Plausible (Maisons-Alfort) |
| Iris 0104 (93030) | PC | 3,882 | 100 | 84 | 92 | 86 | Plausible |
| Moret-sur-Loing (77316) | GC | 3,066 | 100 | 82 | 95 | 85 | Distant exurb, about 70 km SE |
| Est-Sud-Ouest (77183) | GC | 2,470 | 100 | 79 | 99 | 84 | Value-trap candidate |
| Boussy-Saint-Antoine (91097) | GC | 2,858 | 100 | 79 | 100 | 84 | Whole-commune unit (see note) |
| Mairie-Morangis (91161) | GC | 2,848 | 100 | 79 | 99 | 84 | Value-trap candidate |
| Survilliers (95604) | GC | 2,545 | 100 | 79 | 94 | 84 | Distant exurb, thin market |
| Hardricourt (78299) | GC | 3,152 | 100 | 83 | 81 | 84 | Whole-commune unit |
| Le Coudray-Montceaux (91179) | GC | 3,000 | 100 | 80 | 93 | 84 | Distant exurb |
| La Source-Cimetière (77122) | GC | 3,111 | 100 | 80 | 89 | 84 | Value-trap candidate |

About two of the top 20 are plausible inner-ring transitional IRIS. The rest are cheap Grande-Couronne communes, every one with Value 100. They are not attractive on fundamentals; they are maximally discounted by a location-blind model.

Two artefacts to flag:

1. The Value-equals-100 monoculture. 98% of the top 200 carry a saturated Value score. When one input pins to its ceiling for a quarter of the universe, it stops discriminating and just selects on price.
2. The "commune non irisée" unit bias. Small communes that are not subdivided into IRIS appear as one large unit that aggregates hundreds of sales (Boussy-Saint-Antoine is 535 sales in one unit), which inflates the count-based Rental and Risk scores against a single Paris micro-IRIS. Liquidity should be normalised per dwelling or area, not taken as a raw count.

Rental is mislabelled. In `institutional.py` the rental sub-score is computed from liquidity (transaction count) only. The actual rent series `loyer_m2` is never used, because it is stored with European comma decimals ("32,67…") and `pd.to_numeric` turns every value into NaN (0 of 5,264 parse as is; 5,255 parse after the comma is fixed). So "rental demand" today means "how many sales happened," not rent.

Toxicity is dead weight. `inst_toxicity` appears in neither `INSTITUTIONAL_W` nor `ALPHA_W`, so it influences no ranking. As defined (falling price plus thin trading) it also comes out lower in the Grande Couronne (47.6) than Paris (53.0), which is backwards for the institutional concern.

## Step 3: value-trap framework

The defect to neutralise: observed price far below expected does not imply opportunity. In Île-de-France most cheap outer communes are cheap for durable reasons, including weak demand, car dependence, thin resale markets, and demographic stagnation.

VALUE_TRAP_SCORE (0 = clean, 100 = severe) is a weighted blend of the fundamentals that, when weak, turn cheapness into a trap:

| Component | Weight | Source available today |
|---|---:|---|
| Weak appreciation | 0.30 | 100 minus appreciation (momentum plus ML forecast) |
| Weak rental demand | 0.25 | 100 minus rental (real rent plus liquidity) |
| High toxicity | 0.20 | inst_toxicity (falling price plus thin trading) |
| Illiquidity | 0.15 | 100 minus liquidity (transaction depth) |
| Weak risk profile | 0.10 | 100 minus inst_risk (volatility, thinness) |

Trap-adjusted value used downstream: `value_adj = value_raw × (1 − 0.85 × trap/100)`. Cheapness counts only to the extent the fundamentals are sound.

Stated data gap: the brief lists population and employment trend as trap inputs. The `demographics` and `income` tables hold a single year (2023), so trend measures cannot be computed today (`pop_cagr` is 100% NaN). The trap score proxies decline through momentum, toxicity, and liquidity. Adding a multi-year census and FiLoSoFi pull is the highest-value data fix to complete it.

Result: 1,194 of 5,264 IRIS (23%) score trap at or above 60; 94 of those sit in the production top 20% on Alpha. The largest demotions under the prototype are tiny exurban communes at €1,500 to €3,000 per m² (Voulton, Thénisy, Le Plessis-Placy, Barbey) falling from about the 90th to about the 10th Alpha percentile.

## Step 4: reassess the weighting

The current weights over-reward cheapness and under-weight demand, liquidity, and quality:

| Component | Production Institutional | Production Alpha (nominal, effective) | Issue |
|---|---:|---:|---|
| Appreciation | 0.30 | 0.35 to 0.44 | momentum off a low base; ML forecast unused |
| Value | 0.20 | 0.25 to 0.31 | the mis-specified, location-blind input |
| Rental | 0.25 | 0.10 to 0.125 | measures liquidity, not rent |
| Development | 0.15 | 0.10 to 0.125 | neutral across the periphery |
| Risk | 0.10 | not used | a 10% buffer, never gated |
| Transit | not used | 0.20, dropped | always None, silently renormalised away |
| Liquidity | not used | not used | not an explicit factor |
| Toxicity | not used | not used | computed but unused |

Production Alpha sets the 20% transit term to None; `_wavg` renormalises over the present terms, so the effective weights are larger than written and Value rises to about 31%. That is a hidden over-weighting.

Recommended weights (prototype): let Value enter only in its trap-adjusted form, add explicit liquidity, and let appreciation, rental, and risk carry the screen.

| Component | New Institutional | New Alpha |
|---|---:|---:|
| Appreciation (momentum plus ML forecast) | 0.28 | 0.40 |
| Rental (real rent plus liquidity) | 0.22 | 0.20 |
| Risk | 0.15 | not used |
| Value (trap-adjusted) | 0.15 | 0.15 |
| Development | 0.10 | 0.15 |
| Liquidity | 0.10 | 0.10 |

## Step 5: quality gates

A single strong factor must not promote a structurally weak location. Gates apply after weighting, as caps then penalties:

| Rule | Action |
|---|---|
| Appreciation below 40 | cap the final score at 55 |
| Rental below 40 | cap the final score at 55 |
| Toxicity above 70 | multiply by 0.85 |
| Risk below 30 | multiply by 0.85 |
| Liquidity below 15 (very thin) | multiply by 0.85 |
| Any trap risk | multiply by (1 − 0.40 × trap/100) |

This answers the brief's examples directly and stops Value, or any one factor, from dominating. It is transparent and auditable rather than a black-box refit.

## Step 6: investor profiles

Five leaderboards over the cleaned sub-scores, all trap-gated. The zone mix of each profile's top 200 confirms they behave as intended:

| Profile | Emphasis | Top-200 zone mix | Median €/m² |
|---|---|---|---:|
| Core | rental .30, risk .25, liquidity .20, appr .15, value .10 | Paris 18%, PC 29%, GC 52% | 4,402 |
| Growth | appr .45, dev .20, rental .15, value .10, liq .10 | Paris 5%, PC 35%, GC 60% | 3,782 |
| Value | value_adj .45, appr .20, rental .15, risk .10, liq .10 | Paris 0%, PC 28%, GC 72% | 3,560 |
| Developer | dev .45, appr .20, value .15, liq .10, rental .10 | Paris 2%, PC 44%, GC 55% | 3,879 |
| Institutional | balanced (Step 4) | Paris 4%, PC 30%, GC 66% | 3,724 |

Core tilts toward Paris and higher-priced, liquid stock. The Value book, now trap-penalised, still leans cheap and Grande Couronne but no longer on saturated discounts. The Developer book concentrates in the Petite Couronne, where buildability data exists.

## Step 7: benchmark against real markets

Mean Alpha percentile for the named proven corridors, before and after:

| Commune | Median €/m² | Alpha pct, current | Alpha pct, prototype | Trap |
|---|---:|---:|---:|---:|
| Boulogne-Billancourt | 8,845 | 21 | 62 | 42 |
| Issy-les-Moulineaux | 8,250 | 22 | 60 | 44 |
| Saint-Ouen | 6,612 | 34 | 55 | 46 |
| Clichy | 7,314 | 21 | 38 | 50 |
| Pantin | 6,456 | 39 | 43 | 54 |
| Montreuil | 5,855 | 36 | 38 | 55 |

Why the current model ranks distressed exurbs above proven corridors: the corridors are expensive, so the location-blind hedonic marks them "overvalued" (Value 0 to 16) and the discount-driven Alpha buries them; the exurbs are cheap, so they max out Value and float up. The prototype lifts the corridors into the upper-middle band, their genuine trap-checked profile, and demotes the exurbs. Pantin and Montreuil rise only modestly, which is fair: at trap 54 to 55 they carry real softness that a disciplined screen should not ignore.

## Step 8: rebuilt Alpha

Definition: Alpha is the probability of strong risk-adjusted appreciation over 5 to 15 years, not "how discounted is it today."

The current Alpha fails this: r = +0.87 with the broken Value, -0.73 with price level, and -0.66 with actual rent (it rewards lower rents), and it silently discards a 20% transit weight that is always None.

Rebuilt Alpha (prototype):

```
appreciation = 0.5 ML_forecast_CAGR(pct) + 0.5 historical_momentum(pct)
rental       = 0.6 real_rent(pct)        + 0.4 liquidity(pct)
alpha_base   = 0.40 appreciation + 0.20 rental + 0.15 development
             + 0.15 value_adj + 0.10 liquidity
alpha        = gates(alpha_base)
```

Key changes: wire in the existing `ml_forecast` (`expected_price_cagr`), which the project already produces but does not use in scoring; value enters only trap-adjusted; toxicity and illiquidity become real penalties; the dead transit term is removed, or replaced by a true transit proxy once station-distance data is wired in.

Regime note: in this 2026 dataset the ML forecast is negative across all of Île-de-France (median CAGR Paris -7.5%, PC -5.7%, GC -4.6%), so the forward term ranks locations by least-bad outlook. That is correct for a relative screen, but the absolute message, a broadly cooling market, should be shown to investors alongside the ranking, not hidden by it.

## Step 9: recommendations, impact, and before/after

1. Current weaknesses. Location-blind hedonic, so Value equals negative price level; Rental measures liquidity not rent (a comma-decimal parse bug kills the rent series); Toxicity computed but unused; no quality gates; Alpha silently drops a 20% transit weight and correlates 0.87 with the broken Value; NaN-to-50 fills hide geographic data gaps; count-based liquidity inflates whole-commune units.
2. Statistical findings. Value is degenerate by band (median 0 / 52 / 100); Alpha and Institutional rise outward and downmarket; the top-200 Alpha is 98% Value at or above 95, 75% Grande Couronne, median €3,293; correlations alpha~price -0.73, alpha~value +0.87, value~price -0.85, alpha~rent -0.66.
3. Value-trap analysis. The new score flags 1,194 of 5,264 (23%) at trap 60 or higher; 94 are in the current Alpha top 20%. The biggest demotions are €1.5k to €3k exurban communes (about the 90th to the 10th percentile).
4. Recommended weights. Institutional: appr .28, rental .22, risk .15, value_adj .15, dev .10, liquidity .10. Alpha: appr .40, rental .20, dev .15, value_adj .15, liquidity .10.
5. Recommended penalties. Toxicity above 70, multiply by 0.85; Risk below 30, multiply by 0.85; Liquidity below 15, multiply by 0.85; trap haircut, multiply by (1 − 0.40 × trap/100).
6. Recommended gates. Appreciation below 40, cap at 55; Rental below 40, cap at 55.
7. New Alpha. As Step 8: forward (ML) plus momentum plus demand plus development plus trap-adjusted value, gated, transit term fixed.
8. Expected impact. The top-200 zone mix shifts from Grande Couronne 75% / PC 25% / Paris 0% (current Alpha) to Grande Couronne 64% / PC 32% / Paris 4% (new Alpha). The periphery is reduced but not banished, and Paris stops being categorically excluded. The median price of the top 200 rises only modestly (€3,293 to €3,735): the model is not simply flipping to expensive Paris (Paris is only 4% of the new top 200). It removes the weakest cheap units and admits sound mid-priced ones.
9. Example before/after, Alpha top names.

Before (production): Moret-sur-Loing, Survilliers, Boussy-Saint-Antoine, Hardricourt, Le Coudray-Montceaux, all cheap exurbs with Value 100.

After (prototype):

| IRIS | Band | €/m² | Appr | Rental | Trap | Alpha |
|---|---|---:|---:|---:|---:|---:|
| République (94017) | PC | 3,926 | 86 | 67 | 19 | 76 |
| Pleyel 01 (93066) | PC | 5,474 | 91 | 74 | 11 | 76 |
| Village Pierre Lais (94060) | PC | 3,958 | 91 | 65 | 14 | 75 |
| Tremblay 1 (94017) | PC | 5,085 | 84 | 70 | 16 | 75 |
| Ouest-Sud (77464) | GC | 3,586 | 91 | 53 | 18 | 71 |
| Alfred Sisley (92078) | PC | 4,125 | 84 | 76 | 19 | 71 |
| Les Neufs Saulets (94044) | PC | 3,472 | 83 | 65 | 18 | 71 |
| Gare-Brèche aux Loups (77350) | GC | 4,022 | 90 | 54 | 18 | 70 |
| Paris Chennevières (94019) | PC | 4,607 | 78 | 64 | 21 | 70 |
| Centre Ville (95052) | GC | 2,969 | 89 | 51 | 19 | 70 |

The new leaderboard reads like an institutional pipeline: Pleyel in Saint-Denis (the Grand Paris Express super-hub and Olympic-village regeneration), République, Tremblay, transitional inner-ring markets with demand and transport, not maximally discounted exurbs.

## My assessment, score by score

| Score | Grade | Rationale |
|---|:--:|---|
| Value | F | Location-blind hedonic, so it equals negative price level; the root defect |
| Alpha | F | r = +0.87 with broken Value; drops 20% transit; rewards cheapness and low rent |
| Rental | D | Measures transaction count, not rent; the rent series is dead (parse bug) |
| Institutional | D | Value-driven, no gates, monotonic in geography |
| Development | D (outside Paris) | coverage_ratio is 100% NaN in the Grande Couronne, so it is a neutral filler |
| Toxicity | Incomplete | Computed but used nowhere; the sign is counter-intuitive |
| Appreciation | C | Reasonable idea; momentum off a low base, supply mostly missing, ML forecast unused |
| Risk | C | Volatility plus liquidity is sound, but only a 10% buffer and not gated |
| Attractiveness | C minus | Stable across bands only because it is dominated by neutral-50 fills |

## Implementation status

Implemented on 2026-06-24 in the production scoring: items 2, 3, 4, and 5 in full, and item 1 in its interim form (Value is now trap-gated; the full location-aware hedonic re-derivation is the larger follow-up). Items 6, 7, and 8 are deferred (data and scope). Changed files: `rei/scoring/institutional.py`, `rei/scoring/files_engine.py`, `tests/test_scoring.py`. The `institutional_score` and `alpha_score` columns now carry the gated, trap-aware values, and two columns are added: `value_trap_score` and `inst_value_adj`.

Follow-up plan, in priority order:

1. Interim done. Re-derive the hedonic expected price with location controls (commune or IRIS fixed effects, or income, transit, and zone covariates), so the discount measures mispricing given location rather than raw price level. Until then, Value is trap-gated.
2. Done. Make `rental` use the real rent series, parsed.
3. Done. Fix the `loyer_m2` European-decimal parse at the merge in `files_engine.py`, so rent feeds both engines.
4. Done. Add the value-trap score, the quality gates and penalties, the rebalanced weights, and wire `inst_toxicity` in through the trap score and the toxicity gate.
5. Done. Wire `ml_forecast.expected_price_cagr` into Alpha and remove the dead None transit term.
6. Deferred. Normalise liquidity per dwelling or area to remove the whole-commune ("commune non irisée") inflation.
7. Deferred. Add multi-year census and FiLoSoFi so population, income, and employment trends exist; today they are single-year and neutralised.
8. Deferred. Reconsider the NaN-to-50 fill in `indicators.percentile_score`, which hides coverage gaps; prefer explicit coverage flags. This primitive has a test contract, so change it carefully.

Reproduce the figures with:

```
python3 analysis/ranking_review.py
# writes analysis/before_after_rankings.csv and analysis/value_trap_flags.csv
```

## Appendix: artefacts

- `analysis/ranking_review.py`, a read-only prototype that does not touch production code.
- `analysis/before_after_rankings.csv`, every IRIS with old and new scores and the five profile scores.
- `analysis/value_trap_flags.csv`, the IRIS flagged at trap 60 or higher.
