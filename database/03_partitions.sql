-- DVF partitioned by mutation_year (large table; year-scoped queries).

CREATE TABLE IF NOT EXISTS core.dvf_transactions (
    mutation_year             smallint NOT NULL,
    id_mutation               text NOT NULL,
    id_parcelle               text NOT NULL,
    type_local                text NOT NULL,
    date_mutation             date,
    nature_mutation           text,
    valeur_fonciere           double precision,
    code_commune              text,
    code_departement          text,
    surface_reelle_bati       double precision,
    nombre_pieces_principales double precision,
    surface_terrain           double precision,
    longitude                 double precision,
    latitude                  double precision,
    prix_m2                   double precision,
    PRIMARY KEY (mutation_year, id_mutation, id_parcelle, type_local)
) PARTITION BY RANGE (mutation_year);

-- Yearly partitions (extend as new millesimes publish).
DO $$
DECLARE y int;
BEGIN
    FOR y IN 2014..2027 LOOP
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS core.dvf_%s PARTITION OF core.dvf_transactions '
            'FOR VALUES FROM (%s) TO (%s);', y, y, y + 1);
    END LOOP;
END $$;

-- Catch-all so an out-of-range year never breaks an insert.
CREATE TABLE IF NOT EXISTS core.dvf_default PARTITION OF core.dvf_transactions DEFAULT;
