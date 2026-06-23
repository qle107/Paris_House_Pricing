-- Core tabular schema (column names match ingestion collectors).

-- Reference dimension: one row per geographic unit (commune / arrondissement /
-- IRIS / EPCI), with a self-referencing parent for roll-ups.
CREATE TABLE IF NOT EXISTS core.geo_unit (
    geo_code     text PRIMARY KEY,
    level        text NOT NULL CHECK (level IN ('iris','commune','arrondissement','epci','departement','region')),
    name         text,
    parent_code  text,
    population    integer,          -- denormalised latest legal population (convenience)
    updated_at   timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_geo_unit_level  ON core.geo_unit(level);
CREATE INDEX IF NOT EXISTS ix_geo_unit_parent ON core.geo_unit(parent_code);

-- Generic long-format socio-economic tables (one indicator per row).
-- Long format keeps the schema stable across INSEE millesimes & indicators.
CREATE TABLE IF NOT EXISTS core.demographics (
    geo_code  text NOT NULL,
    year      smallint NOT NULL,
    indicator text NOT NULL,
    value     double precision,
    PRIMARY KEY (geo_code, year, indicator)
);
CREATE TABLE IF NOT EXISTS core.employment (LIKE core.demographics INCLUDING ALL);
CREATE TABLE IF NOT EXISTS core.income      (LIKE core.demographics INCLUDING ALL);
CREATE TABLE IF NOT EXISTS core.migration   (LIKE core.demographics INCLUDING ALL);
CREATE TABLE IF NOT EXISTS core.households  (LIKE core.demographics INCLUDING ALL);
CREATE TABLE IF NOT EXISTS core.amenities   (LIKE core.demographics INCLUDING ALL);

-- Building permits (supply signal), commune x month grain.
CREATE TABLE IF NOT EXISTS core.permits (
    code_commune        text NOT NULL,
    month               date NOT NULL,
    permits             integer,
    logements_autorises double precision,
    PRIMARY KEY (code_commune, month)
);

-- Asking rents (commune grain, latest snapshot).
CREATE TABLE IF NOT EXISTS core.rents (
    code_commune      text PRIMARY KEY,
    loypredm2         double precision,    -- predicted EUR/m2/month (all types)
    loypredm2_appart  double precision,
    loypredm2_maison  double precision
);

-- Natural / technological risk (commune grain).
CREATE TABLE IF NOT EXISTS core.risk (
    code_commune text PRIMARY KEY,
    n_risques    integer,
    inondation   boolean,
    argiles      boolean,
    risques      text
);

-- DPE energy certificates (address grain, surrogate key).
CREATE TABLE IF NOT EXISTS core.dpe (
    dpe_row_id                 bigint PRIMARY KEY,
    code_commune               text,
    classe_dpe                 text,
    surface_habitable_logement double precision,
    annee_construction         integer
);
CREATE INDEX IF NOT EXISTS ix_dpe_commune ON core.dpe(code_commune);

-- Schools + IPS (UAI key).
CREATE TABLE IF NOT EXISTS core.schools (
    uai                text PRIMARY KEY,
    code_commune       text,
    ips                double precision,
    nom_etablissement  text
);
CREATE INDEX IF NOT EXISTS ix_schools_commune ON core.schools(code_commune);

-- Crime (surrogate key; long format by offence class & year).
CREATE TABLE IF NOT EXISTS core.crime (
    crime_row_id   bigint PRIMARY KEY,
    code_commune   text,
    annee          integer,
    classe         text,
    faits          double precision,
    taux_pour_mille double precision
);
CREATE INDEX IF NOT EXISTS ix_crime_commune ON core.crime(code_commune);

-- Municipal finance (surrogate key; long format by aggregate & year).
CREATE TABLE IF NOT EXISTS core.municipal_finance (
    fin_row_id   bigint PRIMARY KEY,
    code_commune text,
    year         integer,
    agregat      text,
    montant      double precision
);
CREATE INDEX IF NOT EXISTS ix_munfin_commune ON core.municipal_finance(code_commune);

-- SIRENE establishments (siret key).
CREATE TABLE IF NOT EXISTS core.establishments (
    siret        text PRIMARY KEY,
    code_commune text,
    date_creation date,
    naf          text
);
CREATE INDEX IF NOT EXISTS ix_estab_commune ON core.establishments(code_commune);

-- FDI projects (surrogate key).
CREATE TABLE IF NOT EXISTS core.fdi_projects (
    fdi_row_id bigint PRIMARY KEY,
    region     text,
    year       integer,
    secteur    text,
    emplois    integer
);

-- Ingestion observability + incremental watermarks.
CREATE TABLE IF NOT EXISTS meta.ingestion_log (
    id          bigserial PRIMARY KEY,
    source_id   text NOT NULL,
    rows_loaded integer,
    status      text NOT NULL,          -- 'ok' | 'error'
    detail      text,                   -- error msg, or 'watermark=YYYY-MM-DD'
    run_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_inglog_source ON meta.ingestion_log(source_id, run_at DESC);
