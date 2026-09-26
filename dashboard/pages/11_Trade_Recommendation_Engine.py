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
    page_title="Trade Recommendation Engine",
    layout="wide"
)

st.title(
    "🚀 Trade Recommendation Engine"
)

st.markdown(
    """
    Generate actionable BUY / SELL / HOLD
    recommendations using:

    • Portfolio Holdings

    • Recommended Allocations

    • Factor Scores

    • Hybrid Valuation Estimates
    """
)

# ==========================================
# Database
# ==========================================

conn = sqlite3.connect(
    DB_PATH
)

# ==========================================
# Load Position Data
# ==========================================

query = """
SELECT

    ra.ticker,

    ra.overall_score,

    ra.recommended_shares,

    ra.current_price,

    COALESCE(pp.shares, 0) AS current_shares,

    iv.hybrid_score,

    iv.estimated_upside_pct,

    iv.estimated_fair_value

FROM recommended_allocations ra

LEFT JOIN portfolio_positions pp
       ON ra.ticker = pp.ticker

LEFT JOIN intrinsic_values iv
       ON ra.ticker = iv.ticker
"""

df = pd.read_sql_query(
    query,
    conn
)

conn.close()

# ==========================================
# Empty Check
# ==========================================

if df.empty:

    st.warning(
        "No allocation data found."
    )

    st.stop()

# ==========================================
# Calculations
# ==========================================

df["share_difference"] = (

    df["recommended_shares"]

    -

    df["current_shares"]

)

df["trade_value"] = (

    df["share_difference"]

    *

    df["current_price"]

)

# ==========================================
# Trade Logic
# ==========================================

def determine_action(row):

    if row["share_difference"] > 1:

        return "BUY"

    elif row["share_difference"] < -1:

        return "SELL"

    return "HOLD"


df["action"] = (

    df.apply(
        determine_action,
        axis=1
    )

)

# ==========================================
# Metrics
# ==========================================

buy_count = len(
    df[
        df["action"] == "BUY"
    ]
)

sell_count = len(
    df[
        df["action"] == "SELL"
    ]
)

hold_count = len(
    df[
        df["action"] == "HOLD"
    ]
)

buy_value = round(
    df[
        df["trade_value"] > 0
    ]["trade_value"].sum(),
    2
)

sell_value = round(
    abs(
        df[
            df["trade_value"] < 0
        ]["trade_value"].sum()
    ),
    2
)

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "BUY Signals",
    buy_count
)

c2.metric(
    "SELL Signals",
    sell_count
)

c3.metric(
    "Capital Required",
    f"${buy_value:,.0f}"
)

c4.metric(
    "Capital Freed",
    f"${sell_value:,.0f}"
)

# ==========================================
# Top Recommendations
# ==========================================

st.divider()

st.subheader(
    "⭐ Highest Conviction Opportunities"
)

top_df = df.sort_values(

    by=[
        "overall_score",
        "estimated_upside_pct"
    ],

    ascending=False

).head(20)

st.dataframe(

    top_df[
        [

            "ticker",

            "overall_score",

            "hybrid_score",

            "estimated_upside_pct",

            "current_price",

            "action"

        ]
    ],

    hide_index=True,

    use_container_width=True

)

# ==========================================
# BUY Recommendations
# ==========================================

st.divider()

st.subheader(
    "🟢 BUY Recommendations"
)

buy_df = df[
    df["action"] == "BUY"
]

if buy_df.empty:

    st.info(
        "No Buy Recommendations"
    )

else:

    buy_df = buy_df.sort_values(

        by=[
            "overall_score",
            "estimated_upside_pct"
        ],

        ascending=False

    )

    st.dataframe(

        buy_df[
            [

                "ticker",

                "overall_score",

                "hybrid_score",

                "estimated_upside_pct",

                "current_shares",

                "recommended_shares",

                "share_difference",

                "trade_value"

            ]
        ],

        hide_index=True,

        use_container_width=True

    )

# ==========================================
# SELL Recommendations
# ==========================================

st.divider()

st.subheader(
    "🔴 SELL Recommendations"
)

sell_df = df[
    df["action"] == "SELL"
]

if sell_df.empty:

    st.info(
        "No Sell Recommendations"
    )

else:

    st.dataframe(

        sell_df[
            [

                "ticker",

                "overall_score",

                "estimated_upside_pct",

                "current_shares",

                "recommended_shares",

                "share_difference",

                "trade_value"

            ]
        ],

        hide_index=True,

        use_container_width=True

    )

# ==========================================
# HOLD Recommendations
# ==========================================

st.divider()

st.subheader(
    "🟡 HOLD Recommendations"
)

hold_df = df[
    df["action"] == "HOLD"
]

if not hold_df.empty:

    st.dataframe(

        hold_df[
            [

                "ticker",

                "overall_score",

                "estimated_upside_pct",

                "current_shares",

                "recommended_shares"

            ]
        ],

        hide_index=True,

        use_container_width=True

    )

# ==========================================
# Trade Impact Chart
# ==========================================

st.divider()

st.subheader(
    "💰 Trade Impact"
)

chart_df = (

    df[
        df["action"] != "HOLD"
    ]

    .set_index(
        "ticker"
    )[
        "trade_value"
    ]

)

if not chart_df.empty:

    st.bar_chart(
        chart_df
    )

# ==========================================
# Export Trade Sheet
# ==========================================

st.divider()

trade_sheet = df[
    df["action"] != "HOLD"
]

st.download_button(

    "📥 Download Trade Sheet",

    trade_sheet.to_csv(
        index=False
    ),

    file_name=
    "trade_recommendations.csv",

    mime="text/csv"
)

# ==========================================
# Best Opportunities
# ==========================================

st.divider()

st.subheader(
    "🔥 Best Risk / Reward Ideas"
)

best = df.sort_values(

    by=[
        "estimated_upside_pct",
        "overall_score"
    ],

    ascending=False

).head(15)

st.dataframe(

    best[
        [

            "ticker",

            "overall_score",

            "hybrid_score",

            "estimated_upside_pct",

            "estimated_fair_value"

        ]
    ],

    hide_index=True,

    use_container_width=True

)

# ==========================================
# Footer
# ==========================================

st.divider()

st.caption(
    """
    Recommendations generated from:

    • Factor Ratings

    • Fundamental Metrics

    • Momentum Metrics

    • Hybrid Valuation Model

    • Recommended Allocations

    • Portfolio Holdings
    """
)
