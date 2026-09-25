import streamlit as st
import sqlite3
import pandas as pd

from pathlib import Path

# ==========================================
# Configuration
# ==========================================

ROOT = Path(__file__).resolve().parent.parent.parent

DB_PATH = ROOT / "InvestmentAdvisor.db"

# ==========================================
# Page
# ==========================================

st.set_page_config(
    page_title="Top Ranked Stocks",
    layout="wide"
)

st.title(
    "🏆 Top Ranked Stocks"
)

st.markdown(
    """
    View the highest ranked stocks from the
    multi-factor model.
    """
)

# ==========================================
# Filters
# ==========================================

col1, col2 = st.columns(2)

with col1:

    minimum_score = st.slider(
        "Minimum Overall Score",
        min_value=0,
        max_value=100,
        value=70
    )

with col2:

    max_rows = st.selectbox(
        "Rows To Display",
        [
            25,
            50,
            100,
            250
        ],
        index=1
    )

# ==========================================
# Load Data
# ==========================================

try:

    conn = sqlite3.connect(
        DB_PATH
    )

    query = """
    SELECT

        ticker,

        value_score,

        quality_score,

        growth_score,

        momentum_score,

        overall_score

    FROM analytics_scores

    WHERE overall_score >= ?

    ORDER BY overall_score DESC

    LIMIT ?
    """

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
        f"Unable to load rankings:\n{e}"
    )

    st.stop()

# ==========================================
# Metrics
# ==========================================

if not df.empty:

    top_score = (
        df["overall_score"]
        .max()
    )

    avg_score = round(
        df["overall_score"]
        .mean(),
        2
    )

    stock_count = len(df)

    m1, m2, m3 = st.columns(3)

    m1.metric(
        "Stocks Displayed",
        stock_count
    )

    m2.metric(
        "Highest Score",
        f"{top_score:.2f}"
    )

    m3.metric(
        "Average Score",
        avg_score
    )

# ==========================================
# Rankings Table
# ==========================================

st.divider()

st.subheader(
    "Factor Rankings"
)

if df.empty:

    st.warning(
        "No stocks match current filters."
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
# Strong Buy Section
# ==========================================

st.divider()

st.subheader(
    "⭐ Strong Buy Candidates"
)

strong_buys = df[
    df["overall_score"] >= 80
]

if strong_buys.empty:

    st.info(
        "No strong buys found."
    )

else:

    st.dataframe(

        strong_buys,

        use_container_width=True,

        hide_index=True

    )

# ==========================================
# Download CSV
# ==========================================

st.divider()

csv = df.to_csv(
    index=False
)

st.download_button(

    label="📥 Download Rankings CSV",

    data=csv,

    file_name="top_ranked_stocks.csv",

    mime="text/csv"

)

# ==========================================
# Score Distribution
# ==========================================

st.divider()

st.subheader(
    "Overall Score Distribution"
)

if not df.empty:

    st.bar_chart(
        df.set_index(
            "ticker"
        )[
            "overall_score"
        ]
    )

# ==========================================
# Footer
# ==========================================

st.divider()

st.caption(
    "Ranks generated using Value, Quality, Growth and Momentum factors."
)
