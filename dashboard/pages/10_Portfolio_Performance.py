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
    page_title="Portfolio Performance",
    layout="wide"
)

st.title(
    "📈 Portfolio Performance"
)

st.markdown(
    """
    View current portfolio value,
    gains/losses, sector exposure,
    and position performance.
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

query = """
WITH latest_prices AS (

    SELECT

        p1.ticker,

        p1.close_price

    FROM prices p1

    INNER JOIN (

        SELECT

            ticker,

            MAX(price_date) AS max_date

        FROM prices

        GROUP BY ticker

    ) p2

    ON p1.ticker = p2.ticker

    AND p1.price_date = p2.max_date

)

SELECT

    pp.ticker,

    pp.shares,

    pp.average_cost,

    cu.company_name,

    cu.sector,

    lp.close_price

FROM portfolio_positions pp

LEFT JOIN company_universe cu
ON pp.ticker = cu.ticker

LEFT JOIN latest_prices lp
ON pp.ticker = lp.ticker
"""

df = pd.read_sql_query(
    query,
    conn
)

conn.close()

# ==========================================
# Empty Portfolio
# ==========================================

if df.empty:

    st.warning(
        "No portfolio positions found."
    )

    st.stop()

# ==========================================
# Calculations
# ==========================================

df["cost_basis"] = (

    df["shares"]

    *

    df["average_cost"]

)

df["market_value"] = (

    df["shares"]

    *

    df["close_price"]

)

df["gain_loss"] = (

    df["market_value"]

    -

    df["cost_basis"]

)

df["return_pct"] = (

    df["gain_loss"]

    /

    df["cost_basis"]

) * 100

# ==========================================
# Portfolio Metrics
# ==========================================

total_cost = round(
    df["cost_basis"].sum(),
    2
)

portfolio_value = round(
    df["market_value"].sum(),
    2
)

gain_loss = round(
    portfolio_value
    -
    total_cost,
    2
)

gain_pct = round(

    (
        gain_loss
        /
        total_cost
    )

    * 100,

    2

) if total_cost else 0

winning_positions = len(

    df[
        df["gain_loss"] > 0
    ]

)

total_positions = len(df)

win_rate = round(

    (
        winning_positions
        /
        total_positions
    )

    * 100,

    1

)

# ==========================================
# Dashboard Metrics
# ==========================================

m1, m2, m3, m4 = st.columns(4)

m1.metric(
    "Portfolio Value",
    f"${portfolio_value:,.0f}"
)

m2.metric(
    "Cost Basis",
    f"${total_cost:,.0f}"
)

m3.metric(
    "Gain / Loss",
    f"${gain_loss:,.0f}",
    f"{gain_pct:.1f}%"
)

m4.metric(
    "Win Rate",
    f"{win_rate}%"
)

# ==========================================
# Position Detail
# ==========================================

st.divider()

st.subheader(
    "🏦 Portfolio Holdings"
)

display_df = df[
    [

        "ticker",

        "company_name",

        "sector",

        "shares",

        "average_cost",

        "close_price",

        "cost_basis",

        "market_value",

        "gain_loss",

        "return_pct"

    ]

].sort_values(

    "market_value",

    ascending=False

)

st.dataframe(

    display_df,

    hide_index=True,

    use_container_width=True

)

# ==========================================
# Winners
# ==========================================

st.divider()

st.subheader(
    "🟢 Top Winners"
)

winners = df.sort_values(

    "return_pct",

    ascending=False

).head(10)

st.dataframe(

    winners[
        [

            "ticker",

            "market_value",

            "gain_loss",

            "return_pct"

        ]
    ],

    hide_index=True,

    use_container_width=True

)

# ==========================================
# Losers
# ==========================================

st.divider()

st.subheader(
    "🔴 Largest Losers"
)

losers = df.sort_values(

    "return_pct"

).head(10)

st.dataframe(

    losers[
        [

            "ticker",

            "market_value",

            "gain_loss",

            "return_pct"

        ]
    ],

    hide_index=True,

    use_container_width=True

)

# ==========================================
# Sector Allocation
# ==========================================

st.divider()

st.subheader(
    "🏭 Sector Allocation"
)

sector_df = (

    df.groupby(
        "sector"
    )

    ["market_value"]

    .sum()

    .reset_index()

)

sector_df["allocation_pct"] = (

    sector_df["market_value"]

    /

    portfolio_value

) * 100

st.dataframe(

    sector_df,

    hide_index=True,

    use_container_width=True

)

st.bar_chart(

    sector_df.set_index(
        "sector"
    )[
        "allocation_pct"
    ]

)

# ==========================================
# Portfolio Allocation Chart
# ==========================================

st.divider()

st.subheader(
    "📊 Position Sizes"
)

position_chart = (

    df.sort_values(

        "market_value",

        ascending=False

    )

    .set_index(
        "ticker"
    )[
        "market_value"
    ]

)

st.bar_chart(
    position_chart
)

# ==========================================
# Export
# ==========================================

st.divider()

st.download_button(

    "📥 Export Portfolio Performance",

    display_df.to_csv(
        index=False
    ),

    file_name=
    "portfolio_performance.csv",

    mime="text/csv"

)

# ==========================================
# Footer
# ==========================================

st.divider()

st.caption(
    """
    Portfolio performance calculated from:

    • Robinhood Holdings

    • Historical Prices

    • Company Universe
    """
)
