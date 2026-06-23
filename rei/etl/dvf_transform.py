"""National DVF cleaning with Polars and DuckDB."""
from __future__ import annotations

from pathlib import Path

import duckdb
import polars as pl

RESIDENTIAL = ["Appartement", "Maison"]


def clean_national(csv_path: str | Path, out_parquet: str | Path) -> Path:
    """Stream-clean the national DVF CSV to a tidy residential Parquet file."""
    lf = (
        pl.scan_csv(csv_path, infer_schema_length=10_000, ignore_errors=True)
        .filter(pl.col("type_local").is_in(RESIDENTIAL))
        .with_columns(
            pl.col("date_mutation").str.to_date(strict=False),
            pl.col("valeur_fonciere").cast(pl.Float64, strict=False),
            pl.col("surface_reelle_bati").cast(pl.Float64, strict=False),
        )
        .filter((pl.col("valeur_fonciere") > 5000) & (pl.col("surface_reelle_bati") > 8))
        .with_columns(
            (pl.col("valeur_fonciere") / pl.col("surface_reelle_bati")).round(0).alias("prix_m2"),
            pl.col("date_mutation").dt.year().alias("mutation_year"),
        )
        .filter(pl.col("prix_m2").is_between(200, 25_000))
        .unique(subset=["id_mutation", "id_parcelle", "type_local"])
    )
    out_parquet = Path(out_parquet)
    lf.sink_parquet(out_parquet)
    return out_parquet


def commune_year_medians(parquet_path: str | Path) -> pl.DataFrame:
    """DuckDB median price/m2 per commune-year directly off Parquet."""
    con = duckdb.connect()
    df = con.execute(
        f"""
        SELECT code_commune,
               mutation_year,
               count(*)                       AS n_sales,
               median(prix_m2)                AS median_prix_m2,
               quantile_cont(prix_m2, 0.25)   AS p25,
               quantile_cont(prix_m2, 0.75)   AS p75
        FROM read_parquet('{parquet_path}')
        GROUP BY code_commune, mutation_year
        ORDER BY code_commune, mutation_year
        """
    ).pl()
    con.close()
    return df
