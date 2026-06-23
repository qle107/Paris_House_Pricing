-- Feature pull for rei/scoring/engine.py (one row per commune).
SELECT code_commune,
       name,
       population,
       pop_cagr,
       revenu_median,
       median_prix_m2_last,
       price_cagr_5y,
       permits_per_1000,
       loyer_m2,
       n_risques,
       ips_mean,
       zoning_share_au
FROM scores.mv_commune_features
WHERE population >= :min_population;
