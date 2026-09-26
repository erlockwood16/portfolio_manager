import streamlit as st
import sqlite3
import pandas as pd

from pathlib import Path

# ==========================================
# Configuration
# ==========================================

ROOT = Path(__file__).resolve().parent.parent.parent

DB_PATH = ROOT / "InvestmentAdvisor.db"

st.set_page_config(
    page_title="Fundamental Screener",
    layout="wide"
)

st.title(
    "🔎 Fundamental Screener"
)

# ==========================================
# Filters
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
    ["All"] +
    sector_df["sector"]
    .dropna()
    .tolist()
)

min_revenue_growth = st.slider(
    "Minimum Revenue Growth %",
    -50,
    100,
    10
)

min_roa = st.slider(
    "Minimum ROA %",
    -20,
    50,
    5
)

max_debt = st.slider(
    "Maximum Debt Ratio %",
    0,
    100,
    80
)

min_score = st.slider(
    "Minimum Overall Score",
    0,
    100,
    75
)

# ==========================================
# Query
# ==========================================

query = """
SELECT

    cu.ticker,

    cu.company_name,

    cu.sector,

    fm.revenue_growth,

    fm.earnings_growth,

    fm.net_margin,

    fm.roa,

    fm.debt_ratio,

    a.overall_score,

    a.momentum_score,

    iv.current_price,

    iv.estimated_fair_value,

    iv.estimated_upside_pct,

    iv.hybrid_score

FROM company_universe cu

JOIN fundamental_metrics fm
ON cu.ticker = fm.ticker

JOIN analytics_scores a
ON cu.ticker = a.ticker

LEFT JOIN intrinsic_values iv
ON cu.ticker = iv.ticker

WHERE

    fm.revenue_growth >= ?

    AND fm.roa >= ?

    AND fm.debt_ratio <= ?

    AND a.overall_score >= ?
"""

params = [

    min_revenue_growth,

    min_roa,

    max_debt,

    min_score

]

if sector != "All":

    query += """

    AND cu.sector = ?
    """

    params.append(
        sector
    )

query += """

ORDER BY

    a.overall_score DESC,

    iv.estimated_upside_pct DESC
"""

df = pd.read_sql_query(
    query,
    conn,
    params=params
)

conn.close()

# ==========================================
# Metrics
# ==========================================

col1, col2, col3 = st.columns(3)

col1.metric(
    "Companies Found",
    len(df)
)

if not df.empty:

    col2.metric(
        "Avg Score",
        round(
            df["overall_score"]
            .mean(),
            1
        )
    )

    col3.metric(
        "Avg Upside",
        f"{round(df['estimated_upside_pct'].mean(),1)}%"
    )

# ==========================================
# Results
# ==========================================

st.divider()

st.dataframe(

    df,

    use_container_width=True,

    hide_index=True

)

# ==========================================
# Strongest Opportunities
# ==========================================

st.divider()

st.subheader(
    "⭐ Top 20 Opportunities"
)

top20 = df.head(20)

if not top20.empty:

    st.bar_chart(

        top20.set_index(
            "ticker"
        )[
            "overall_score"
        ]

    )

# ==========================================
# Download
# ==========================================

st.divider()

st.download_button(

    "📥 Download Screener Results",

    df.to_csv(
        index=False
    ),

    file_name=
    "fundamental_screener.csv",

    mime="text/csv"
)

# ==========================================
# Footer
# ==========================================

st.divider()

st.caption(
    "Filtered using SEC fundamentals, momentum metrics, factor scores and hybrid valuation estimates."
)
