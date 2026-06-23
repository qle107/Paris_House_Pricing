"""AI agent DAG: crawl, embed, extract, alerts."""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator

default_args = {"owner": "rei", "retries": 2, "retry_delay": timedelta(minutes=15)}


def _communes() -> list[str]:
    return Variable.get("rei_communes", default_var="93066,93070,94043,92050").split(",")


def crawl(**_):
    from rei.ai_agent.crawler import download_pending
    download_pending(limit=100)


def embed(**_):
    from sqlalchemy import text
    from rei.ai_agent.rag import embed_document
    from rei.common.db import get_engine
    with get_engine().connect() as c:
        ids = [r[0] for r in c.execute(text("SELECT id FROM docs.document WHERE status='fetched' LIMIT 200"))]
    for i in ids:
        embed_document(i)


def extract(**_):
    from config.settings import settings
    if settings.llm_provider == "manual":
        return  # human-in-the-loop; see rei.ai_agent.run export-prompt / ingest
    from rei.ai_agent.extractors import extract_auto
    for c in _communes():
        extract_auto(c)


def alerts(**_):
    from rei.ai_agent.alerts import generate_alerts
    generate_alerts(_communes())


with DAG(
    dag_id="rei_ai_agent",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule="0 6 * * 1",          # weekly, Monday 06:00
    catchup=False,
    tags=["rei", "ai", "zoning"],
) as dag:
    t_crawl = PythonOperator(task_id="crawl", python_callable=crawl)
    t_embed = PythonOperator(task_id="embed", python_callable=embed)
    t_extract = PythonOperator(task_id="extract", python_callable=extract)
    t_alerts = PythonOperator(task_id="alerts", python_callable=alerts)
    t_crawl >> t_embed >> t_extract >> t_alerts
