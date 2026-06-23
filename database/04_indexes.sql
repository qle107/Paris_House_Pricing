-- GiST on spatial layers; B-tree on filter columns.

-- GiST indexes
CREATE INDEX IF NOT EXISTS gix_parcels_geom    ON gis.parcels            USING gist (geometry);
CREATE INDEX IF NOT EXISTS gix_buildings_geom  ON gis.buildings          USING gist (geometry);
CREATE INDEX IF NOT EXISTS gix_zoning_geom     ON gis.zoning             USING gist (geometry);
CREATE INDEX IF NOT EXISTS gix_stops_geom      ON gis.transit_stops      USING gist (geometry);
CREATE INDEX IF NOT EXISTS gix_projects_geom   ON gis.transport_projects USING gist (geometry);

-- B-tree filters
CREATE INDEX IF NOT EXISTS ix_parcels_commune  ON gis.parcels(code_commune);
CREATE INDEX IF NOT EXISTS ix_zoning_commune   ON gis.zoning(code_commune);
CREATE INDEX IF NOT EXISTS ix_zoning_capture   ON gis.zoning(code_commune, captured_at);

-- DVF: commune + date are the hot filters within each yearly partition.
CREATE INDEX IF NOT EXISTS ix_dvf_commune_date ON core.dvf_transactions(code_commune, date_mutation);
CREATE INDEX IF NOT EXISTS ix_dvf_parcelle     ON core.dvf_transactions(id_parcelle);

-- Long-format socio-economic: filter by indicator + year.
CREATE INDEX IF NOT EXISTS ix_demo_ind  ON core.demographics(indicator, year);
CREATE INDEX IF NOT EXISTS ix_emp_ind   ON core.employment(indicator, year);
CREATE INDEX IF NOT EXISTS ix_inc_ind   ON core.income(indicator, year);

-- Fuzzy document title search (pg_trgm) for the AI agent.
CREATE INDEX IF NOT EXISTS ix_doc_url_trgm ON docs.document USING gin (source_url gin_trgm_ops);
