-- PostGIS schema (EPSG:4326 storage; EPSG:2154 for metric ops).

-- Cadastral parcels = the spatial backbone everything joins to.
CREATE TABLE IF NOT EXISTS gis.parcels (
    id_parcelle  text NOT NULL,
    code_commune text NOT NULL,
    section      text,
    numero       text,
    contenance   double precision,           -- cadastral area (m2)
    geometry     geometry(Geometry, 4326),
    PRIMARY KEY (id_parcelle)
);

CREATE TABLE IF NOT EXISTS gis.buildings (
    code_commune text,
    geometry     geometry(Geometry, 4326)
);

-- PLU/PLUi zoning snapshots. `captured_at` lets us keep successive versions
-- so plu_diff can detect reclassifications over time.
CREATE TABLE IF NOT EXISTS gis.zoning (
    code_commune text,
    libelle      text,            -- zone code e.g. "UA", "AU", "1AUb"
    libelong     text,
    typezone     text,            -- U / AUc / AUs / A / N (normalised family)
    destdomi     text,
    partition    text,            -- GPU document id (commune/PLUi)
    captured_at  timestamptz,
    geometry     geometry(Geometry, 4326)
);

CREATE TABLE IF NOT EXISTS gis.transit_stops (
    network   text,
    stop_id   text,
    stop_name text,
    geometry  geometry(Point, 4326)
);

-- Forward-looking transport projects (stations/lines + opening date).
CREATE TABLE IF NOT EXISTS gis.transport_projects (
    project      text,
    line         text,
    station      text,
    mode         text,
    opening      date,
    status       text,               -- planned / under_construction / commissioning
    code_dept    text,
    commune      text,
    description  text,
    impact_score double precision,    -- 0-100 (rei.transport.impact.project_impact_score)
    source       text,
    geometry     geometry(Geometry, 4326)
);

CREATE TABLE IF NOT EXISTS gis.scot (
    code_commune text,
    libelle      text,
    captured_at  timestamptz,
    geometry     geometry(Geometry, 4326)
);

CREATE TABLE IF NOT EXISTS gis.zac (
    code_commune text,
    libelle      text,
    captured_at  timestamptz,
    geometry     geometry(Geometry, 4326)
);

-- Forward-looking urban-development operations (ZAC, districts, facilities).
CREATE TABLE IF NOT EXISTS gis.development_projects (
    project      text,
    project_type text,               -- business_district / mixed_use_district / hospital / university / ...
    status       text,               -- planned / approved / under_construction / completed
    completion   date,
    code_dept    text,
    commune      text,
    description  text,
    impact_score double precision,    -- 0-100 (rei.development.projects.dev_impact_score)
    source       text,
    geometry     geometry(Geometry, 4326)
);
