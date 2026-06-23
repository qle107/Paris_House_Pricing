-- Low permits/capita + rising pop/price CAGR = tight supply.
SELECT f.code_commune,
       f.name,
       f.population,
       f.pop_cagr,
       f.price_cagr_5y,
       s.permits_per_1000,
       -- simple tightness ratio: demand growth per unit of new supply
       (COALESCE(f.pop_cagr,0) + COALESCE(f.price_cagr_5y,0))
         / NULLIF(s.permits_per_1000, 0) AS tightness_ratio
FROM scores.mv_commune_features f
JOIN scores.mv_supply s ON s.code_commune = f.code_commune
WHERE f.population >= 5000
ORDER BY tightness_ratio DESC NULLS LAST
LIMIT 200;
