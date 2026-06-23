#!/usr/bin/env bash
# Runs at first container start (mounted into /docker-entrypoint-initdb.d).
# Creates the Airflow metadata DB, then applies the REI schema in order.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-SQL
    CREATE DATABASE airflow;
SQL

for f in \
    00_extensions.sql \
    01_schema_core.sql \
    02_schema_gis.sql \
    03_partitions.sql \
    06_vector.sql \
    04_indexes.sql \
    07_map.sql \
    05_materialized_views.sql
do
    echo "Applying /sql/$f"
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f "/sql/$f"
done
