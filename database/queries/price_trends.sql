-- Median price/m² and volume by commune and year.
SELECT code_commune,
       mutation_year,
       count(*)                                              AS n_sales,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY prix_m2)  AS median_prix_m2,
       percentile_cont(0.25) WITHIN GROUP (ORDER BY prix_m2) AS p25_prix_m2,
       percentile_cont(0.75) WITHIN GROUP (ORDER BY prix_m2) AS p75_prix_m2,
       avg(surface_reelle_bati)                              AS surface_moy
FROM core.dvf_transactions
WHERE prix_m2 BETWEEN 200 AND 25000
  AND (:communes IS NULL OR code_commune = ANY(:communes))
GROUP BY code_commune, mutation_year
ORDER BY code_commune, mutation_year;
