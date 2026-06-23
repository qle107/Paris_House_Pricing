"""Schema validation and anomaly checks for loaded data."""
from __future__ import annotations

import pandas as pd
from pandera import Check, Column, DataFrameSchema

from rei.common.db import record_ingestion
from rei.common.logging import get_logger

log = get_logger(__name__)

dvf_schema = DataFrameSchema(
    {
        "valeur_fonciere": Column(float, Check.gt(0)),
        "surface_reelle_bati": Column(float, Check.gt(0)),
        "prix_m2": Column(float, Check.in_range(200, 25_000)),
        "type_local": Column(str, Check.isin(["Appartement", "Maison"])),
        "mutation_year": Column("Int64", Check.in_range(2014, 2030), nullable=False),
        "code_commune": Column(str, Check.str_length(min_value=5, max_value=5)),
    },
    coerce=True,
)

permits_schema = DataFrameSchema(
    {
        "code_commune": Column(str, Check.str_length(5, 5)),
        "logements_autorises": Column(float, Check.ge(0), nullable=True),
    },
    coerce=True,
)


def validate_dvf(df: pd.DataFrame) -> pd.DataFrame:
    """Raise SchemaError on contract violation; return validated frame."""
    return dvf_schema.validate(df, lazy=True)


def robust_z(series: pd.Series) -> pd.Series:
    med = series.median()
    mad = (series - med).abs().median() or 1e-9
    return 0.6745 * (series - med) / mad


def flag_price_jumps(price_trend: pd.DataFrame, z_thresh: float = 4.0) -> pd.DataFrame:
    """Flag commune-years whose median price/m2 YoY change is an outlier."""
    df = price_trend.sort_values(["code_commune", "mutation_year"]).copy()
    df["yoy"] = df.groupby("code_commune")["median_prix_m2"].pct_change()
    df["z"] = robust_z(df["yoy"].fillna(0))
    flagged = df[df["z"].abs() > z_thresh]
    if not flagged.empty:
        record_ingestion(
            "dvf_transactions", len(flagged), "ok",
            detail=f"anomaly: {len(flagged)} commune-year price jumps |z|>{z_thresh}",
        )
        log.warning("Flagged %d anomalous price jumps", len(flagged))
    return flagged


def missingness_report(df: pd.DataFrame) -> pd.DataFrame:
    """Per-column missing-value share, for the data-quality dashboard."""
    out = df.isna().mean().mul(100).round(2)
    out = out.rename_axis("column").reset_index(name="pct_missing")
    return out.sort_values("pct_missing", ascending=False)
