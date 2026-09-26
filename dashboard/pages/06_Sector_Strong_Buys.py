import streamlit as st
import sqlite3
import pandas as pd

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

DB_PATH = ROOT / "InvestmentAdvisor.db"

st.set_page_config(
    page_title="Sector Strong Buys",
    layout="wide"
)

st.title(
    "⭐ Sector Strong Buys"
)

# ==========================================
# Database
# ==========================================

conn = sqlite3.connect(
    DB_PATH
)

sector_df = pd.read_sql_query(
    """
    SELECT DISTINCT sector
    FROM company_universe
    ORDER BY sector
    """,
    conn
)

sector = st.selectbox(
    "Sector",
    sector_df["sector"]
)

query = """
SELECT

    cu.ticker,

    cu.company_name,

    a.value_score,

    a.quality_score,

    a.growth_score,

    a.momentum_score,

    a.overall_score

FROM company_universe cu

JOIN analytics_scores a
ON cu.ticker = a.ticker

WHERE cu.sector = ?

ORDER BY a.overall_score DESC

LIMIT 25
"""

df = pd.read_sql_query(
    query,
    conn,
    params=(sector,)
)

conn.close()

st.dataframe(
    df,
    use_container_width=True,
    hide_index=True
)
