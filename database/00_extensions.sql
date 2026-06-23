-- Extensions and schemas (PostGIS + pgvector).
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_raster;
CREATE EXTENSION IF NOT EXISTS btree_gist;     -- composite GiST (geom + scalar)
CREATE EXTENSION IF NOT EXISTS pg_trgm;         -- fuzzy text search on doc names
CREATE EXTENSION IF NOT EXISTS vector;          -- pgvector for the RAG store

CREATE SCHEMA IF NOT EXISTS core;   -- tabular socio-economic / market feeds
CREATE SCHEMA IF NOT EXISTS gis;    -- spatial layers (parcels, zoning, transit)
CREATE SCHEMA IF NOT EXISTS docs;   -- planning documents + RAG chunks
CREATE SCHEMA IF NOT EXISTS scores; -- computed indicators & final scores
CREATE SCHEMA IF NOT EXISTS meta;   -- ingestion log, watermarks, run metadata
