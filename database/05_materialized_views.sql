-- Materialized views for commune-level features (refresh after ingest).

-- Median price/m2 per commune per year + 5y CAGR (price momentum).
DROP MATERIALIZED VIEW IF EXISTS scores.mv_price_trend CASCADE;
CREATE MATERIALIZED VIEW scores.mv_price_trend AS
WITH yearly AS (
    SELECT code_commune,
           mutation_year AS year,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY prix_m2) AS median_prix_m2,
           count(*) AS n_sales
    FROM core.dvf_transactions
    WHERE prix_m2 BETWEEN 200 AND 25000      -- trim absurd outliers
    GROUP BY code_commune, mutation_year
)
SELECT code_commune,
       max(year) AS last_year,
       max(median_prix_m2) FILTER (WHERE year = (SELECT max(year) FROM yearly y2 WHERE y2.code_commune = yearly.code_commune)) AS median_prix_m2_last,
       -- 5y CAGR using first & last available year within the window
       (power(
          NULLIF(max(median_prix_m2) FILTER (WHERE year = (SELECT max(year) FROM yearly)), 0)
          / NULLIF(min(median_prix_m2) FILTER (WHERE year = (SELECT min(year) FROM yearly WHERE year >= (SELECT max(year) FROM yearly) - 5)), 0),
          0.2) - 1) AS price_cagr_5y,
       sum(n_sales) AS n_sales_total
FROM yearly
GROUP BY code_commune;
CREATE UNIQUE INDEX ix_mv_price_trend ON scores.mv_price_trend(code_commune);

-- Housing supply intensity: permits per 1,000 inhabitants, trailing 36 months.
DROP MATERIALIZED VIEW IF EXISTS scores.mv_supply CASCADE;
CREATE MATERIALIZED VIEW scores.mv_supply AS
SELECT p.code_commune,
       sum(p.logements_autorises) AS logements_autorises_36m,
       g.population,
       CASE WHEN g.population > 0
            THEN 1000.0 * sum(p.logements_autorises) / g.population
            ELSE NULL END AS permits_per_1000
FROM core.permits p
LEFT JOIN core.geo_unit g ON g.geo_code = p.code_commune
WHERE p.month >= (CURRENT_DATE - INTERVAL '36 months')
GROUP BY p.code_commune, g.population;
CREATE UNIQUE INDEX ix_mv_supply ON scores.mv_supply(code_commune);

-- Population & income CAGR helpers from the long-format tables.
DROP MATERIALIZED VIEW IF EXISTS scores.mv_demo_cagr CASCADE;
CREATE MATERIALIZED VIEW scores.mv_demo_cagr AS
WITH pop AS (
    SELECT geo_code, year, value
    FROM core.demographics WHERE indicator = 'population'
),
bounds AS (
    SELECT geo_code, min(year) AS y0, max(year) AS y1 FROM pop GROUP BY geo_code
)
SELECT b.geo_code AS code_commune,
       (power(NULLIF(p1.value,0) / NULLIF(p0.value,0), 1.0/NULLIF(b.y1-b.y0,0)) - 1) AS pop_cagr
FROM bounds b
JOIN pop p0 ON p0.geo_code = b.geo_code AND p0.year = b.y0
JOIN pop p1 ON p1.geo_code = b.geo_code AND p1.year = b.y1
WHERE b.y1 > b.y0;
CREATE UNIQUE INDEX ix_mv_demo_cagr ON scores.mv_demo_cagr(code_commune);

-- Wide feature table consumed by the scoring engine.
DROP MATERIALIZED VIEW IF EXISTS scores.mv_commune_features CASCADE;
CREATE MATERIALIZED VIEW scores.mv_commune_features AS
SELECT gu.geo_code AS code_commune,
       gu.name,
       gu.population,
       dc.pop_cagr,
       inc.value           AS revenu_median,
       pt.median_prix_m2_last,
       pt.price_cagr_5y,
       sup.permits_per_1000,
       r.loypredm2         AS loyer_m2,
       rk.n_risques,
       sch.ips_mean,
       zc.share_au         AS zoning_share_au   -- share of commune area zoned AU (future-urbanisable)
FROM core.geo_unit gu
LEFT JOIN scores.mv_demo_cagr dc ON dc.code_commune = gu.geo_code
LEFT JOIN (SELECT geo_code, max(value) AS value FROM core.income WHERE indicator='revenu_median_uc' GROUP BY geo_code) inc
       ON inc.geo_code = gu.geo_code
LEFT JOIN scores.mv_price_trend pt ON pt.code_commune = gu.geo_code
LEFT JOIN scores.mv_supply sup     ON sup.code_commune = gu.geo_code
LEFT JOIN core.rents r             ON r.code_commune = gu.geo_code
LEFT JOIN core.risk rk             ON rk.code_commune = gu.geo_code
LEFT JOIN (SELECT code_commune, avg(ips) AS ips_mean FROM core.schools GROUP BY code_commune) sch
       ON sch.code_commune = gu.geo_code
LEFT JOIN (
    SELECT code_commune,
           sum(ST_Area(geometry::geography)) FILTER (WHERE typezone ILIKE 'AU%')
           / NULLIF(sum(ST_Area(geometry::geography)), 0) AS share_au
    FROM gis.zoning
    GROUP BY code_commune
) zc ON zc.code_commune = gu.geo_code
WHERE gu.level = 'commune';
CREATE UNIQUE INDEX ix_mv_features ON scores.mv_commune_features(code_commune);
