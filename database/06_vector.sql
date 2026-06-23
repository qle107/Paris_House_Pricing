-- Document store + pgvector (768-dim, matches REI_EMBED_MODEL).

-- One row per discovered/downloaded planning document.
CREATE TABLE IF NOT EXISTS docs.document (
    id            bigserial PRIMARY KEY,
    code_commune  text,
    doc_type      text,          -- plu | plui | scot | deliberation | consultation | sraddet
    source_url    text UNIQUE NOT NULL,
    host          text,
    title         text,
    discovered_at timestamptz DEFAULT now(),
    fetched_at    timestamptz,
    status        text DEFAULT 'discovered',   -- discovered | fetched | parsed | embedded | error
    sha256        text,
    n_pages       integer
);
CREATE INDEX IF NOT EXISTS ix_doc_commune ON docs.document(code_commune, doc_type);
CREATE INDEX IF NOT EXISTS ix_doc_status  ON docs.document(status);

-- Chunked text + embedding for retrieval.
CREATE TABLE IF NOT EXISTS docs.chunk (
    id          bigserial PRIMARY KEY,
    document_id bigint NOT NULL REFERENCES docs.document(id) ON DELETE CASCADE,
    chunk_index integer NOT NULL,
    page_from   integer,
    page_to     integer,
    content     text NOT NULL,
    token_count integer,
    embedding   vector(768),
    UNIQUE (document_id, chunk_index)
);

-- Approximate-nearest-neighbour index (cosine). Build after bulk embedding.
CREATE INDEX IF NOT EXISTS ix_chunk_embedding
    ON docs.chunk USING hnsw (embedding vector_cosine_ops);

-- Structured facts the agent extracts from documents (zoning/density/housing).
CREATE TABLE IF NOT EXISTS docs.extraction (
    id           bigserial PRIMARY KEY,
    document_id  bigint REFERENCES docs.document(id) ON DELETE CASCADE,
    code_commune text,
    fact_type    text,        -- density_increase | rezoning | housing_target | transport | redevelopment
    payload      jsonb,       -- structured details from the LLM
    confidence   double precision,
    created_at   timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_extraction_commune ON docs.extraction(code_commune, fact_type);
