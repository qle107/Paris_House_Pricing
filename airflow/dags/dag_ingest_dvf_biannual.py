"""DVF refresh DAG (biannual upstream, monthly check)."""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator

default_args = {"owner": "rei", "retries": 2, "retry_delay": timedelta(minutes=30)}


def _communes() -> list[str]:
    return Variable.get("rei_communes", default_var="93066,93070,94043,92050").split(",")


def ingest(source_id: str, **_):
    from rei.ingestion.registry import get_collector
    get_collector(source_id).run(communes=_communes())


def rescore(**_):
    from rei.etl.load import refresh_matviews
    from rei.scoring.engine import score
    from rei.zoning.detectors import score_communes
    refresh_matviews()
    score("value_add_opportunistic", density_scores=score_communes(_communes()))


with DAG(
    dag_id="rei_ingest_dvf_biannual",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule="0 3 1 * *",          # 1st of each month, 03:00 (cheap no-op if no new release)
    catchup=False,
    tags=["rei", "dvf", "cadastre", "zoning"],
) as dag:
    dvf = PythonOperator(task_id="ingest_dvf", python_callable=ingest, op_kwargs={"source_id": "dvf_transactions"})
    cad = PythonOperator(task_id="ingest_cadastre", python_callable=ingest, op_kwargs={"source_id": "cadastre_parcels"})
    gpu = PythonOperator(task_id="ingest_zoning", python_callable=ingest, op_kwargs={"source_id": "gpu_zoning"})
    sc = PythonOperator(task_id="rescore", python_callable=rescore)
    [dvf, cad, gpu] >> sc
