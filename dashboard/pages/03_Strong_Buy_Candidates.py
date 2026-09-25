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
    page_title="Strong Buy Candidates",
    layout="wide"
)

# ==========================================
# Header
# ==========================================

st.title(
    "⭐ Strong Buy Candidates"
)

st.markdown(
    """
    Stocks meeting Strong Buy thresholds from
    the multi-factor ranking engine.
    """
)

# ==========================================
# Controls
# ==========================================

col1, col2 = st.columns(2)

with col1:

    minimum_score = st.slider(
        "Minimum Overall Score",
        min_value=80,
        max_value=100,
        value=80
    )

with col2:

    max_rows = st.selectbox(
        "Rows To Display",
        [10, 25, 50, 100],
        index=1
    )

# ==========================================
# Query
# ==========================================

query = """
SELECT

    a.ticker,

    a.value_score,

    a.quality_score,

    a.growth_score,

    a.momentum_score,

    a.overall_score,

    f.pe_ratio,

    f.price_to_book,

    f.revenue_growth,

    f.earnings_growth,

    p.close_price

FROM analytics_scores a

LEFT JOIN fundamentals f
       ON a.ticker = f.ticker

LEFT JOIN (

    SELECT
        ticker,
        close_price
    FROM prices
    WHERE price_date = (
        SELECT MAX(price_date)
        FROM prices p2
        WHERE p2.ticker = prices.ticker
    )

) p

ON a.ticker = p.ticker

WHERE a.overall_score >= ?

ORDER BY a.overall_score DESC

LIMIT ?
"""

# ==========================================
# Load Data
# ==========================================

try:

    conn = sqlite3.connect(
        DB_PATH
    )

    df = pd.read_sql_query(

        query,

        conn,

        params=(
            minimum_score,
            max_rows
        )

    )

    conn.close()

except Exception as e:

    st.error(
        f"Unable to load candidates:\n{e}"
    )

    st.stop()

# ==========================================
# Metrics
# ==========================================

st.divider()

if not df.empty:

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Strong Buys",
        len(df)
    )

    col2.metric(
        "Highest Score",
        round(
            df["overall_score"].max(),
            2
        )
    )

    col3.metric(
        "Average Score",
        round(
            df["overall_score"].mean(),
            2
        )
    )

# ==========================================
# Candidate Table
# ==========================================

st.divider()

st.subheader(
    "Strong Buy Universe"
)

if df.empty:

    st.warning(
        "No strong buys found."
    )

else:

    df.insert(
        0,
        "Rank",
        range(
            1,
            len(df) + 1
        )
    )

    st.dataframe(

        df,

        use_container_width=True,

        hide_index=True

    )

# ==========================================
# Top 10 Focus List
# ==========================================

st.divider()

st.subheader(
    "🎯 Top 10 Focus List"
)

top10 = df.head(10)

if not top10.empty:

    st.dataframe(

        top10[
            [
                "Rank",
                "ticker",
                "overall_score",
                "value_score",
                "quality_score",
                "growth_score",
                "momentum_score"
            ]
        ],

        hide_index=True,

        use_container_width=True

    )

# ==========================================
# Factor Breakdown
# ==========================================

st.divider()

st.subheader(
    "Factor Breakdown"
)

if not df.empty:

    chart_df = df.set_index(
        "ticker"
    )[
        [
            "value_score",
            "quality_score",
            "growth_score",
            "momentum_score"
        ]
    ]

    st.bar_chart(
        chart_df
    )

# ==========================================
# Export
# ==========================================

st.divider()

csv = df.to_csv(
    index=False
)

st.download_button(

    label="📥 Download Strong Buy List",

    data=csv,

    file_name="strong_buy_candidates.csv",

    mime="text/csv"

)

# ==========================================
# Buy Threshold Logic
# ==========================================

with st.expander(
    "Strong Buy Criteria"
):

    st.markdown(
        """
        Current criteria:

        * Overall Score ≥ 80

        Ranking factors:

        * Value Score
        * Quality Score
        * Growth Score
        * Momentum Score

        Overall Score:

        * 30% Value
        * 30% Quality
        * 20% Growth
        * 20% Momentum
        """
    )

# ==========================================
# Footer
# ==========================================

st.divider()

st.caption(
    "Use this list to build research memos, investment theses and portfolio allocations."
)
