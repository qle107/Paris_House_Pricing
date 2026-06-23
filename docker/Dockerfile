# Application image: ingestion, ETL, GIS, scoring, ML, AI agent, dashboard.
# GDAL/GEOS/PROJ are needed by geopandas/rasterio/shapely.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        gdal-bin libgdal-dev libgeos-dev libproj-dev proj-data proj-bin \
        build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Airflow is NOT in requirements.txt (it runs in the apache/airflow image); the
# app image installs only the platform deps.
RUN pip install -r requirements.txt

COPY . .
RUN pip install -e .

# Default: show CLI help. Override `command:` in compose for real jobs.
CMD ["python", "-m", "rei.cli", "list-sources"]
