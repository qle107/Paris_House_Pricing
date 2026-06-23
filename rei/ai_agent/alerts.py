"""Ranked investment alerts from document extractions and density signals."""
from __future__ import annotations

import pandas as pd
from sqlalchemy import text

from rei.common.db import get_engine
from rei.common.logging import get_logger
from rei.zoning.detectors import score_communes

log = get_logger(__name__)


def recent_extractions(days: int = 30, min_conf: float = 0.6) -> pd.DataFrame:
    sql = text(
        """
        SELECT code_commune, fact_type, payload, confidence, created_at
        FROM docs.extraction
        WHERE created_at >= now() - (:d || ' days')::interval
          AND confidence >= :c
          AND fact_type IN ('rezoning','density_increase','housing_target','transport','redevelopment')
        ORDER BY confidence DESC, created_at DESC
        """
    )
    with get_engine().connect() as conn:
        return pd.read_sql(sql, conn, params={"d": days, "c": min_conf})


def generate_alerts(communes: list[str]) -> pd.DataFrame:
    """Blend document signals + density-change score into one ranked alert feed."""
    extr = recent_extractions()
    dens = score_communes(communes) if communes else pd.DataFrame(columns=["code_commune", "density_change_score"])

    counts = (extr.groupby(["code_commune", "fact_type"]).size().unstack(fill_value=0)
              if not extr.empty else pd.DataFrame())
    alerts = dens.merge(counts, on="code_commune", how="left") if not counts.empty else dens
    alerts = alerts.fillna(0)
    signal_cols = [c for c in alerts.columns if c not in ("code_commune",)]
    alerts["alert_score"] = (
        alerts.get("density_change_score", 0) * 0.6
        + 10 * alerts[[c for c in signal_cols if c != "density_change_score"]].sum(axis=1)
    ).round(1)
    alerts = alerts.sort_values("alert_score", ascending=False)
    if not alerts.empty:
        alerts.to_sql("alert", get_engine(), schema="scores", if_exists="replace", index=False)
        log.info("Generated %d alerts", len(alerts))
    return alerts
