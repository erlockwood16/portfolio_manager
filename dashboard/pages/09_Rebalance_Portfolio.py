import streamlit as st
import sqlite3
import pandas as pd

from pathlib import Path

# ==========================================
# Config
# ==========================================

ROOT = Path(__file__).resolve().parent.parent.parent

DB_PATH = ROOT / "InvestmentAdvisor.db"

st.set_page_config(
    page_title="Rebalance Portfolio",
    layout="wide"
)

st.title(
    "⚖️ Portfolio Rebalancing Engine"
)

st.markdown(
    """
    Compare current Robinhood holdings against
    model allocations and generate trade recommendations.
    """
)

# ==========================================
# Database
# ==========================================

conn = sqlite3.connect(
    DB_PATH
)

# ==========================================
# Load Positions
# ==========================================

positions_query = """
SELECT

    ticker,

    shares,

    average_cost

FROM portfolio_positions
"""

positions = pd.read_sql_query(
    positions_query,
    conn
)

# ==========================================
# Load Allocations
# ==========================================

allocations_query = """
SELECT

    ticker,

    allocation_pct,

    position_value,

    recommended_shares,

    current_price,

    overall_score

FROM recommended_allocations
"""

allocations = pd.read_sql_query(
    allocations_query,
    conn
)

# ==========================================
# Valuation Data
# ==========================================

valuation_query = """
SELECT

    ticker,

    estimated_fair_value,

    estimated_upside_pct,

    hybrid_score

FROM intrinsic_values
"""

valuation = pd.read_sql_query(
    valuation_query,
    conn
)

conn.close()

# ==========================================
# Merge
# ==========================================

comparison = pd.merge(

    allocations,

    positions,

    how="outer",

    on="ticker"

)

comparison = pd.merge(

    comparison,

    valuation,

    how="left",

    on="ticker"

)

# ==========================================
# Clean Values
# ==========================================

comparison["shares"] = (
    comparison["shares"]
    .fillna(0)
)

comparison["recommended_shares"] = (
    comparison["recommended_shares"]
    .fillna(0)
)

comparison["current_price"] = (
    comparison["current_price"]
    .fillna(0)
)

comparison["share_diff"] = (

    comparison["recommended_shares"]

    -

    comparison["shares"]

)

comparison["current_value"] = (

    comparison["shares"]

    *

    comparison["current_price"]

)

comparison["target_value"] = (

    comparison["recommended_shares"]

    *

    comparison["current_price"]

)

comparison["value_diff"] = (

    comparison["target_value"]

    -

    comparison["current_value"]

)

# ==========================================
# Action Logic
# ==========================================

def get_action(row):

    diff = row["share_diff"]

    if diff > 1:

        return "BUY"

    elif diff < -1:

        return "SELL"

    return "HOLD"


comparison["action"] = (

    comparison.apply(
        get_action,
        axis=1
    )

)

# ==========================================
# Summary
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

m1, m2, m3 = st.columns(3)

m1.metric(
    "Buy Orders",
    buy_count
)

m2.metric(
    "Sell Orders",
    sell_count
)

m3.metric(
    "Hold Positions",
    hold_count
)

# ==========================================
# Full Rebalance Table
# ==========================================

st.divider()

st.subheader(
    "📊 Rebalance Analysis"
)

display_cols = [

    "ticker",

    "overall_score",

    "hybrid_score",

    "estimated_upside_pct",

    "shares",

    "recommended_shares",

    "share_diff",

    "current_value",

    "target_value",

    "value_diff",

    "action"

]

st.dataframe(

    comparison[
        display_cols
    ]
    .sort_values(
        "overall_score",
        ascending=False
    ),

    hide_index=True,

    use_container_width=True

)

# ==========================================
# Buy Signals
# ==========================================

st.divider()

st.subheader(
    "🟢 Recommended Buys"
)

buy_df = comparison[
    comparison["action"] == "BUY"
]

if buy_df.empty:

    st.info(
        "No buy signals"
    )

else:

    st.dataframe(

        buy_df[
            [

                "ticker",

                "overall_score",

                "estimated_upside_pct",

                "share_diff",

                "value_diff"

            ]
        ]
        .sort_values(
            "estimated_upside_pct",
            ascending=False
        ),

        hide_index=True,

        use_container_width=True

    )

# ==========================================
# Sell Signals
# ==========================================

st.divider()

st.subheader(
    "🔴 Recommended Sells"
)

sell_df = comparison[
    comparison["action"] == "SELL"
]

if sell_df.empty:

    st.info(
        "No sell signals"
    )

else:

    st.dataframe(

        sell_df[
            [

                "ticker",

                "overall_score",

                "estimated_upside_pct",

                "share_diff",

                "value_diff"

            ]
        ],

        hide_index=True,

        use_container_width=True

    )

# ==========================================
# Highest Conviction Ideas
# ==========================================

st.divider()

st.subheader(
    "⭐ Highest Conviction Opportunities"
)

top = comparison.sort_values(

    by=[
        "overall_score",
        "estimated_upside_pct"
    ],

    ascending=False

).head(10)

st.dataframe(

    top[
        [

            "ticker",

            "overall_score",

            "hybrid_score",

            "estimated_upside_pct",

            "action"

        ]
    ],

    hide_index=True,

    use_container_width=True

)

# ==========================================
# Rebalance Dollar Chart
# ==========================================

st.divider()

st.subheader(
    "💰 Dollars To Rebalance"
)

chart_df = (

    comparison[
        comparison["action"]
        !=
        "HOLD"
    ]

    .set_index(
        "ticker"
    )[
        "value_diff"
    ]

)

if not chart_df.empty:

    st.bar_chart(
        chart_df
    )

# ==========================================
# Export Trades
# ==========================================

st.divider()

trade_df = comparison[
    comparison["action"]
    !=
    "HOLD"
]

st.download_button(

    "📥 Download Trade List",

    trade_df.to_csv(
        index=False
    ),

    file_name=
    "rebalance_trades.csv",

    mime="text/csv"
)

# ==========================================
# Footer
# ==========================================

st.divider()

st.caption(
    """
    Trade recommendations generated from:

    • Current Robinhood Positions

    • Recommended Allocations

    • Factor Scores

    • Hybrid Valuation Model
    """
)
