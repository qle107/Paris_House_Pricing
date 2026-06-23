"""DB bootstrap + materialized-view refresh helpers."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from rei.common.db import get_engine
from rei.common.logging import get_logger

log = get_logger(__name__)

DDL_DIR = Path(__file__).resolve().parents[2] / "database"
DDL_ORDER = [
    "00_extensions.sql",
    "01_schema_core.sql",
    "02_schema_gis.sql",
    "03_partitions.sql",
    "06_vector.sql",
    "04_indexes.sql",
    "07_map.sql",
    "05_materialized_views.sql",
]

MATVIEWS = [
    "scores.mv_price_trend",
    "scores.mv_supply",
    "scores.mv_demo_cagr",
    "scores.mv_commune_features",
]


def bootstrap_database() -> None:
    """Run all DDL files in dependency order (idempotent)."""
    eng = get_engine()
    for fname in DDL_ORDER:
        sql = (DDL_DIR / fname).read_text(encoding="utf-8")
        with eng.begin() as conn:
            conn.execute(text(sql))
        log.info("Applied %s", fname)


def refresh_matviews(concurrently: bool = True) -> None:
    eng = get_engine()
    mode = "CONCURRENTLY" if concurrently else ""
    for mv in MATVIEWS:
        with eng.begin() as conn:
            try:
                conn.execute(text(f"REFRESH MATERIALIZED VIEW {mode} {mv}"))
            except Exception:
                # CONCURRENTLY needs a prior non-concurrent refresh + unique index
                conn.execute(text(f"REFRESH MATERIALIZED VIEW {mv}"))
        log.info("Refreshed %s", mv)


if __name__ == "__main__":
    bootstrap_database()
