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
    page_title="Portfolio Comparison",
    layout="wide"
)

# ==========================================
# Header
# ==========================================

st.title(
    "⚖️ Portfolio Comparison"
)

st.markdown(
    """
    Compare current Robinhood holdings
    against recommended allocations.
    """
)

# ==========================================
# Database
# ==========================================

conn = sqlite3.connect(
    DB_PATH
)

# ==========================================
# Current Holdings
# ==========================================

positions_query = """
SELECT

    ticker,

    shares,

    average_cost,

    total_cost_basis

FROM portfolio_positions

ORDER BY ticker
"""

positions_df = pd.read_sql_query(
    positions_query,
    conn
)

# ==========================================
# Recommended Allocations
# ==========================================

allocations_query = """
SELECT

    ticker,

    overall_score,

    allocation_pct,

    position_value,

    recommended_shares,

    current_price

FROM recommended_allocations

ORDER BY allocation_pct DESC
"""

allocations_df = pd.read_sql_query(
    allocations_query,
    conn
)

conn.close()

# ==========================================
# Metrics
# ==========================================

st.divider()

m1, m2, m3 = st.columns(3)

m1.metric(
    "Current Holdings",
    len(positions_df)
)

m2.metric(
    "Recommended Allocations",
    len(allocations_df)
)

overlap = len(
    set(
        positions_df["ticker"]
    )
    &
    set(
        allocations_df["ticker"]
    )
)

m3.metric(
    "Overlap",
    overlap
)

# ==========================================
# Current Portfolio
# ==========================================

st.divider()

st.subheader(
    "🏦 Current Robinhood Holdings"
)

if positions_df.empty:

    st.warning(
        "No portfolio positions found."
    )

else:

    st.dataframe(

        positions_df,

        use_container_width=True,

        hide_index=True

    )

# ==========================================
# Recommended Portfolio
# ==========================================

st.divider()

st.subheader(
    "🎯 Recommended Allocations"
)

if allocations_df.empty:

    st.warning(
        "No recommended allocations found."
    )

else:

    st.dataframe(

        allocations_df,

        use_container_width=True,

        hide_index=True

    )

# ==========================================
# Portfolio Comparison
# ==========================================

st.divider()

st.subheader(
    "📊 Allocation Comparison"
)

comparison = pd.merge(

    allocations_df,

    positions_df,

    how="outer",

    on="ticker"

)

# Fill missing values

comparison["shares"] = (
    comparison["shares"]
    .fillna(0)
)

comparison["recommended_shares"] = (
    comparison["recommended_shares"]
    .fillna(0)
)

comparison["share_difference"] = (

    comparison["recommended_shares"]

    -

    comparison["shares"]

)

# ==========================================
# Action Logic
# ==========================================

def determine_action(row):

    diff = row["share_difference"]

    if diff > 1:

        return "BUY"

    if diff < -1:

        return "SELL"

    return "HOLD"

comparison["action"] = (

    comparison.apply(
        determine_action,
        axis=1
    )

)

# ==========================================
# Summary Metrics
# ==========================================

buy_count = len(
    comparison[
        comparison["action"] == "BUY"
    ]
)

sell_count = len(
    comparison[
        comparison["action"] == "SELL"
    ]
)

hold_count = len(
    comparison[
        comparison["action"] == "HOLD"
    ]
)

c1, c2, c3 = st.columns(3)

c1.metric(
    "Buy Signals",
    buy_count
)

c2.metric(
    "Sell Signals",
    sell_count
)

c3.metric(
    "Hold Positions",
    hold_count
)

# ==========================================
# Full Analysis
# ==========================================

st.dataframe(

    comparison[
        [

            "ticker",

            "overall_score",

            "shares",

            "recommended_shares",

            "share_difference",

            "allocation_pct",

            "current_price",

            "action"

        ]
    ],

    use_container_width=True,

    hide_index=True

)

# ==========================================
# BUY Signals
# ==========================================

st.divider()

st.subheader(
    "🟢 BUY Signals"
)

buy_df = comparison[
    comparison["action"] == "BUY"
]

if buy_df.empty:

    st.info(
        "No buy signals."
    )

else:

    st.dataframe(

        buy_df[
            [

                "ticker",

                "overall_score",

                "shares",

                "recommended_shares",

                "share_difference",

                "allocation_pct"

            ]
        ],

        use_container_width=True,

        hide_index=True

    )

# ==========================================
# SELL Signals
# ==========================================

st.divider()

st.subheader(
    "🔴 SELL Signals"
)

sell_df = comparison[
    comparison["action"] == "SELL"
]

if sell_df.empty:

    st.info(
        "No sell signals."
    )

else:

    st.dataframe(

        sell_df[
            [

                "ticker",

                "overall_score",

                "shares",

                "recommended_shares",

                "share_difference",

                "allocation_pct"

            ]
        ],

        use_container_width=True,

        hide_index=True

    )

# ==========================================
# Export Recommendations
# ==========================================

st.divider()

trade_df = comparison[
    comparison["action"] != "HOLD"
]

csv = trade_df.to_csv(
    index=False
)

st.download_button(

    "📥 Download Trade Recommendations",

    csv,

    file_name="trade_recommendations.csv",

    mime="text/csv"

)

# ==========================================
# Footer
# ==========================================

st.divider()

st.caption(
    "Robinhood Holdings vs Recommended Allocation Engine"
)
