import streamlit as st
import sqlite3
import pandas as pd

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

DB_PATH = ROOT / "InvestmentAdvisor.db"

st.set_page_config(
    page_title="Sector Heatmap",
    layout="wide"
)

st.title(
    "🔥 Sector Heatmap"
)

conn = sqlite3.connect(
    DB_PATH
)

query = """
SELECT

    cu.sector,

    AVG(a.value_score) AS value_score,

    AVG(a.quality_score) AS quality_score,

    AVG(a.growth_score) AS growth_score,

    AVG(a.momentum_score) AS momentum_score,

    AVG(a.overall_score) AS overall_score

FROM company_universe cu

JOIN analytics_scores a
ON cu.ticker = a.ticker

GROUP BY cu.sector
"""

df = pd.read_sql_query(
    query,
    conn
)

conn.close()

st.dataframe(
    df,
    use_container_width=True,
    hide_index=True
)

st.subheader(
    "Overall Sector Scores"
)

st.bar_chart(
    df.set_index(
        "sector"
    )[
        "overall_score"
    ]
)
