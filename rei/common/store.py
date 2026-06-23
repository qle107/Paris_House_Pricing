"""Parquet/GeoParquet file storage (REI_STORAGE=files)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from config.settings import settings
from rei.common.logging import get_logger

log = get_logger(__name__)


def using_files() -> bool:
    return settings.storage == "files"


def _tables_dir() -> Path:
    p = settings.data_dir / "tables"; p.mkdir(parents=True, exist_ok=True); return p


def _geo_dir() -> Path:
    p = settings.data_dir / "geo"; p.mkdir(parents=True, exist_ok=True); return p


def write_table_files(df: pd.DataFrame, name: str, conflict_cols=None) -> int:
    if df.empty:
        return 0
    path = _tables_dir() / f"{name}.parquet"
    if path.exists():
        old = pd.read_parquet(path)
        combined = pd.concat([old, df], ignore_index=True)
        if conflict_cols:
            keys = [c for c in conflict_cols if c in combined.columns]
            if keys:
                combined = combined.drop_duplicates(subset=keys, keep="last")
    else:
        combined = df
    combined.to_parquet(path, index=False)
    if settings.also_csv or name in ("commune_score", "ml_forecast"):
        combined.to_csv(path.with_suffix(".csv"), index=False)
    log.info("Wrote %d rows -> %s (total %d)", len(df), path.name, len(combined))
    return len(df)


def read_table(name: str) -> pd.DataFrame:
    path = _tables_dir() / f"{name}.parquet"
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


def table_exists(name: str) -> bool:
    return (_tables_dir() / f"{name}.parquet").exists()


def write_geo(gdf, name: str, schema: str = "gis", key: str | None = None) -> int:
    """Dispatch geo writes: GeoParquet in file mode, to_postgis in Postgres mode."""
    if gdf is None or len(gdf) == 0:
        return 0
    if not using_files():
        from rei.common.db import get_engine
        gdf.to_postgis(name, get_engine(), schema=schema, if_exists="append", index=False)
        return len(gdf)

    import geopandas as gpd
    path = _geo_dir() / f"{name}.parquet"
    if path.exists():
        old = gpd.read_parquet(path)
        if key and key in gdf.columns and key in old.columns:
            old = old[~old[key].isin(set(gdf[key]))]
        elif "code_commune" in gdf.columns and "code_commune" in old.columns:
            old = old[~old["code_commune"].isin(set(gdf["code_commune"]))]
        combined = gpd.GeoDataFrame(pd.concat([old, gdf], ignore_index=True), crs=gdf.crs)
    else:
        combined = gdf
    combined.to_parquet(path, index=False)
    log.info("Wrote %d features -> geo/%s.parquet (total %d)", len(gdf), name, len(combined))
    return len(gdf)


def read_geo(name: str):
    import geopandas as gpd
    path = _geo_dir() / f"{name}.parquet"
    return gpd.read_parquet(path) if path.exists() else None


def geo_exists(name: str) -> bool:
    return (_geo_dir() / f"{name}.parquet").exists()


def append_ingestion_log(source_id: str, rows: int, status: str, detail: str = "") -> None:
    path = settings.data_dir / "ingestion_log.csv"
    row = pd.DataFrame([{"source_id": source_id, "rows": rows, "status": status,
                         "detail": detail[:500], "run_at": pd.Timestamp.utcnow()}])
    header = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    row.to_csv(path, mode="a", header=header, index=False)
