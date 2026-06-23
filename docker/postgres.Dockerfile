# PostGIS + pgvector in one image (we need both: spatial layers + RAG store).
FROM postgis/postgis:16-3.4

# pgvector for the docs.chunk embedding column.
RUN apt-get update && apt-get install -y --no-install-recommends \
        postgresql-16-pgvector \
    && rm -rf /var/lib/apt/lists/*
