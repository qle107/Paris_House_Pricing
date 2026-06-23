-- Map layers for vector tiles (commune boundaries, parcel metrics).

-- Commune administrative boundaries (from geo.api.gouv.fr contours).
CREATE TABLE IF NOT EXISTS gis.communes (
    code_commune text PRIMARY KEY,
    name         text,
    geometry     geometry(MultiPolygon, 4326)
);
CREATE INDEX IF NOT EXISTS gix_communes_geom ON gis.communes USING gist (geometry);

-- Persisted parcel-level development metrics (written by rei/gis/persist.py).
CREATE TABLE IF NOT EXISTS scores.parcel_upside (
    id_parcelle         text PRIMARY KEY,
    code_commune        text,
    parcel_area         double precision,
    far_existing        double precision,
    zone_family         text,
    buildable_upside_m2 double precision,
    expected_uplift     double precision,
    geometry            geometry(Geometry, 4326)
);
CREATE INDEX IF NOT EXISTS gix_parcel_upside_geom ON scores.parcel_upside USING gist (geometry);
CREATE INDEX IF NOT EXISTS ix_parcel_upside_commune ON scores.parcel_upside(code_commune);
