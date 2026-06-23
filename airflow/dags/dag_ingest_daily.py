"""Daily ingestion DAG for fast-updating sources."""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "rei",
    "retries": 3,
    "retry_delay": timedelta(minutes=10),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(hours=1),
}


def _communes() -> list[str]:
    return Variable.get("rei_communes", default_var="93066,93070,94043,92050").split(",")


def run_source(source_id: str, **_):
    from rei.ingestion.registry import get_collector
    kwargs = {}
    if source_id in {"transit_gtfs"}:
        kwargs["area_query"] = Variable.get("rei_transit_area", default_var="Ile-de-France")
    elif source_id not in {"insee_population", "insee_employment", "insee_income", "sitadel_permits",
                           "crime_ssmsi", "rental_observatoires"}:
        kwargs["communes"] = _communes()
    get_collector(source_id).run(**kwargs)


def refresh_views(**_):
    from rei.etl.load import refresh_matviews
    refresh_matviews()


def validate(**_):
    import pandas as pd
    from rei.common.db import get_engine
    from rei.etl.validate import flag_price_jumps
    pt = pd.read_sql(
        "SELECT code_commune, mutation_year, "
        "percentile_cont(0.5) WITHIN GROUP (ORDER BY prix_m2) AS median_prix_m2 "
        "FROM core.dvf_transactions GROUP BY code_commune, mutation_year",
        get_engine(),
    )
    flag_price_jumps(pt)


with DAG(
    dag_id="rei_ingest_daily",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule="0 5 * * *",          # 05:00 daily
    catchup=False,
    tags=["rei", "ingest"],
) as dag:
    daily_sources = ["ban_addresses", "transit_gtfs", "georisques", "sirene_businesses",
                     "municipal_minutes", "public_consultations"]
    tasks = [
        PythonOperator(task_id=f"ingest_{s}", python_callable=run_source, op_kwargs={"source_id": s})
        for s in daily_sources
    ]
    refresh = PythonOperator(task_id="refresh_views", python_callable=refresh_views)
    check = PythonOperator(task_id="validate", python_callable=validate)
    tasks >> refresh >> check
