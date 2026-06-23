"""Streamlit dashboard for scores and alerts."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from rei.common.db import get_engine

st.set_page_config(page_title="France RE Intelligence", layout="wide")
eng = get_engine()


@st.cache_data(ttl=600)
def q(sql: str) -> pd.DataFrame:
    return pd.read_sql(sql, eng)


st.title("France Residential & Mixed-Use Intelligence")

tab1, tab2, tab3, tab4 = st.tabs(["City scores", "Alert feed", "Commune deep-dive", "Price forecast"])

with tab1:
    try:
        df = q("SELECT * FROM scores.commune_score ORDER BY attractiveness_score DESC LIMIT 500")
        st.dataframe(df, use_container_width=True)
        st.bar_chart(df.head(20).set_index("name")["attractiveness_score"])
    except Exception as e:
        st.info(f"Run the scoring engine first. ({e})")

with tab2:
    try:
        st.dataframe(q("SELECT * FROM scores.alert ORDER BY alert_score DESC LIMIT 200"),
                     use_container_width=True)
    except Exception as e:
        st.info(f"Run the AI agent alert feed first. ({e})")

with tab3:
    code = st.text_input("INSEE commune code", "93066")
    if code:
        try:
            st.subheader("Median price/m2 by year")
            trend = q(
                f"""SELECT mutation_year AS year,
                           percentile_cont(0.5) WITHIN GROUP (ORDER BY prix_m2) AS median_prix_m2
                    FROM core.dvf_transactions WHERE code_commune='{code}'
                    GROUP BY mutation_year ORDER BY mutation_year"""
            ).set_index("year")
            st.line_chart(trend)
        except Exception as e:
            st.info(f"No data yet for {code}. ({e})")

with tab4:
    try:
        f = q("SELECT * FROM scores.ml_forecast ORDER BY expected_price_cagr DESC")
        st.caption("Forward price-growth forecast (rei.ml): expected CAGR with a p10-p90 band and top drivers.")
        st.dataframe(f, use_container_width=True)
        label = f["name"].fillna(f["code_commune"]) if "name" in f.columns else f["code_commune"]
        st.bar_chart(f.head(20).assign(label=label).set_index("label")["expected_price_cagr"])
    except Exception as e:
        st.info(f"Run `python -m rei.cli train` then `python -m rei.cli predict` first. ({e})")
