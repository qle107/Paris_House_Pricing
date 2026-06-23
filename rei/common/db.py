"""Database access helpers (SQLAlchemy engine + idempotent upsert)."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterable

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from config.settings import settings
from rei.common.logging import get_logger

log = get_logger(__name__)

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.sqlalchemy_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            future=True,
        )
    return _engine


@contextmanager
def connection():
    eng = get_engine()
    with eng.begin() as conn:  # transactional
        yield conn


def upsert_dataframe(
    df: pd.DataFrame,
    table: str,
    conflict_cols: Iterable[str],
    schema: str = "core",
    chunksize: int = 10_000,
) -> int:
    """Idempotent INSERT ... ON CONFLICT via staging table."""
    if settings.storage == "files":
        from rei.common import store
        return store.write_table_files(df, table, conflict_cols)
    if df.empty:
        return 0
    cols = list(df.columns)
    conflict = ", ".join(conflict_cols)
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c not in conflict_cols)
    staging = f"_stg_{table}"

    eng = get_engine()
    with eng.begin() as conn:
        df.to_sql(staging, conn, schema=schema, if_exists="replace", index=False, chunksize=chunksize)
        collist = ", ".join(cols)
        conn.execute(
            text(
                f"INSERT INTO {schema}.{table} ({collist}) "
                f"SELECT {collist} FROM {schema}.{staging} "
                f"ON CONFLICT ({conflict}) DO UPDATE SET {updates}"
                if updates
                else f"INSERT INTO {schema}.{table} ({collist}) "
                f"SELECT {collist} FROM {schema}.{staging} "
                f"ON CONFLICT ({conflict}) DO NOTHING"
            )
        )
        conn.execute(text(f"DROP TABLE {schema}.{staging}"))
    log.info("Upserted %d rows into %s.%s", len(df), schema, table)
    return len(df)


def record_ingestion(source_id: str, rows: int, status: str, detail: str = "") -> None:
    """Best-effort ingestion log; never raises to the caller."""
    if settings.storage == "files":
        from rei.common import store
        store.append_ingestion_log(source_id, rows, status, detail)
        return
    try:
        with connection() as conn:
            conn.execute(
                text(
                    "INSERT INTO meta.ingestion_log (source_id, rows_loaded, status, detail, run_at) "
                    "VALUES (:s, :r, :st, :d, now())"
                ),
                {"s": source_id, "r": rows, "st": status, "d": detail[:2000]},
            )
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not write ingestion_log (%s): %s", source_id, exc)


def last_successful_watermark(source_id: str) -> str | None:
    """Return the most recent watermark stored for a source (incremental loads)."""
    if settings.storage == "files":
        return None
    with connection() as conn:
        row = conn.execute(
            text(
                "SELECT detail FROM meta.ingestion_log "
                "WHERE source_id = :s AND status = 'ok' AND detail LIKE 'watermark=%' "
                "ORDER BY run_at DESC LIMIT 1"
            ),
            {"s": source_id},
        ).fetchone()
    return row[0].split("=", 1)[1] if row else None
