import streamlit as st
import sqlite3
import pandas as pd

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

DB_PATH = ROOT / "InvestmentAdvisor.db"

st.set_page_config(
    page_title="Sector Rankings",
    layout="wide"
)

st.title(
    "🏭 Sector Rankings"
)

# ==========================================
# Load Sector Scores
# ==========================================

conn = sqlite3.connect(
    DB_PATH
)

query = """
SELECT

    cu.sector,

    COUNT(*) AS companies,

    AVG(a.value_score) AS avg_value,

    AVG(a.quality_score) AS avg_quality,

    AVG(a.growth_score) AS avg_growth,

    AVG(a.momentum_score) AS avg_momentum,

    AVG(a.overall_score) AS avg_overall

FROM company_universe cu

JOIN analytics_scores a
ON cu.ticker = a.ticker

GROUP BY
    cu.sector
"""

df = pd.read_sql_query(
    query,
    conn
)

conn.close()

df = df.sort_values(
    "avg_overall",
    ascending=False
)

# ==========================================
# Table
# ==========================================

st.dataframe(
    df,
    use_container_width=True,
    hide_index=True
)

# ==========================================
# Sector Chart
# ==========================================

st.subheader(
    "Sector Strength"
)

chart_df = df.set_index(
    "sector"
)[
    "avg_overall"
]

st.bar_chart(
    chart_df
)
