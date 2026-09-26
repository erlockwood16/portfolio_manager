import streamlit as st
import sqlite3
import subprocess
import sys
import pandas as pd

from pathlib import Path

# ==========================================
# Configuration
# ==========================================

ROOT = Path(__file__).resolve().parent.parent

DB_PATH = ROOT / "InvestmentAdvisor.db"

st.set_page_config(
    page_title="Investment Advisor",
    layout="wide"
)

# ==========================================
# Helper Functions
# ==========================================

def run_daily_update():

    script = ROOT / "jobs" / "daily_update.py"

    return subprocess.run(
        [
            sys.executable,
            str(script)
        ],
        capture_output=True,
        text=True,
        cwd=ROOT
    )


def run_weekly_update():

    script = ROOT / "jobs" / "weekly_update.py"

    return subprocess.run(
        [
            sys.executable,
            str(script)
        ],
        capture_output=True,
        text=True,
        cwd=ROOT
    )


def get_metric(query):

    conn = sqlite3.connect(DB_PATH)

    cursor = conn.cursor()

    cursor.execute(query)

    value = cursor.fetchone()[0]

    conn.close()

    return value


def get_reconciled_cash():

    conn = sqlite3.connect(DB_PATH)

    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        COALESCE(
            cash_balance,
            0
        )
    FROM portfolio_cash
    WHERE source = 'ROBINHOOD'
    """)

    result = cursor.fetchone()

    imported_cash = (
        result[0]
        if result
        else 0
    )

    cursor.execute("""
    SELECT
        COALESCE(
            SUM(amount),
            0
        )
    FROM cash_adjustments
    """)

    result = cursor.fetchone()

    adjustments = (
        result[0]
        if result
        else 0
    )

    conn.close()

    return {

        "imported_cash":
            round(imported_cash, 2),

        "adjustments":
            round(adjustments, 2),

        "reconciled_cash":
            round(
                imported_cash + adjustments,
                2
            )
    }

# ==========================================
# Header
# ==========================================

st.title(
    "📈 Investment Advisor"
)

st.markdown(
    "Portfolio Management & Investment Research Platform"
)

# ==========================================
# Maintenance Controls
# ==========================================

st.divider()

st.subheader(
    "System Maintenance"
)

daily_col, weekly_col = st.columns(2)

# ------------------------------------------
# Daily Update
# ------------------------------------------

with daily_col:

    if st.button(
        "🔄 Run Daily Update",
        type="primary",
        use_container_width=True
    ):

        with st.spinner(
            "Running daily update..."
        ):

            result = run_daily_update()

        if result.returncode == 0:

            st.success(
                "Daily Update Completed Successfully"
            )

            with st.expander(
                "Daily Update Output"
            ):

                st.code(result.stdout)

        else:

            st.error(
                "Daily Update Failed"
            )

            with st.expander(
                "Error Details"
            ):

                st.code(result.stderr)

# ------------------------------------------
# Weekly Update
# ------------------------------------------

with weekly_col:

    if st.button(
        "📊 Run Weekly Update",
        use_container_width=True
    ):

        with st.spinner(
            "Refreshing SEC fundamentals..."
        ):

            result = run_weekly_update()

        if result.returncode == 0:

            st.success(
                "Weekly Update Completed Successfully"
            )

            with st.expander(
                "Weekly Update Output"
            ):

                st.code(result.stdout)

        else:

            st.error(
                "Weekly Update Failed"
            )

            with st.expander(
                "Error Details"
            ):

                st.code(result.stderr)

# ==========================================
# Dashboard Metrics
# ==========================================

st.divider()

st.subheader(
    "Dashboard Metrics"
)

try:

    buy_candidates = get_metric("""
    SELECT COUNT(*)
    FROM buy_candidates
    """)

    research_queue = get_metric("""
    SELECT COUNT(*)
    FROM research_queue
    WHERE status='PENDING'
    """)

    allocations = get_metric("""
    SELECT COUNT(*)
    FROM recommended_allocations
    """)

    cash_info = get_reconciled_cash()

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Buy Candidates",
        buy_candidates
    )

    col2.metric(
        "Research Queue",
        research_queue
    )

    col3.metric(
        "Recommended Allocations",
        allocations
    )

    col4.metric(
        "Reconciled Cash",
        f"${cash_info['reconciled_cash']:,.2f}"
    )

except Exception as e:

    st.warning(
        f"Unable to load dashboard metrics:\n{e}"
    )

# ==========================================
# Cash Reconciliation
# ==========================================

st.divider()

st.subheader(
    "Cash Reconciliation"
)

try:

    cash_info = get_reconciled_cash()

    cash_col1, cash_col2, cash_col3 = st.columns(3)

    cash_col1.metric(
        "Imported Cash",
        f"${cash_info['imported_cash']:,.2f}"
    )

    cash_col2.metric(
        "Adjustments",
        f"${cash_info['adjustments']:,.2f}"
    )

    cash_col3.metric(
        "Actual Cash",
        f"${cash_info['reconciled_cash']:,.2f}"
    )

except Exception as e:

    st.warning(
        f"Unable to load cash reconciliation:\n{e}"
    )

# ==========================================
# Cash Adjustment History
# ==========================================

st.subheader(
    "Cash Adjustment History"
)

try:

    conn = sqlite3.connect(DB_PATH)

    adjustment_query = """
    SELECT

        adjustment_date,
        amount,
        notes

    FROM cash_adjustments

    ORDER BY adjustment_date DESC
    """

    adjustment_df = pd.read_sql(
        adjustment_query,
        conn
    )

    conn.close()

    if not adjustment_df.empty:

        st.dataframe(
            adjustment_df,
            use_container_width=True
        )

    else:

        st.info(
            "No cash adjustments recorded."
        )

except Exception:

    st.info(
        "No cash adjustment history available."
    )

# ==========================================
# Recommended Allocations
# ==========================================

st.divider()

st.subheader(
    "Recommended Portfolio Allocations"
)

try:

    conn = sqlite3.connect(DB_PATH)

    allocation_query = """
    SELECT

        ticker,

        overall_score,

        allocation_pct,

        position_value,

        recommended_shares,

        fair_value,

        upside_pct

    FROM recommended_allocations

    ORDER BY allocation_pct DESC,
             overall_score DESC
    """

    allocation_df = pd.read_sql(
        allocation_query,
        conn
    )

    conn.close()

    if not allocation_df.empty:

        st.dataframe(
            allocation_df,
            use_container_width=True
        )

    else:

        st.info(
            "No allocation recommendations found."
        )

except Exception as e:

    st.warning(
        f"Unable to load allocations:\n{e}"
    )

# ==========================================
# Buy Candidates
# ==========================================

st.divider()

st.subheader(
    "Top Buy Candidates"
)

try:

    conn = sqlite3.connect(DB_PATH)

    buy_query = """
    SELECT

        ticker,

        overall_score,

        recommendation

    FROM buy_candidates

    ORDER BY overall_score DESC

    LIMIT 10
    """

    buy_df = pd.read_sql(
        buy_query,
        conn
    )

    conn.close()

    if not buy_df.empty:

        st.dataframe(
            buy_df,
            use_container_width=True
        )

    else:

        st.info(
            "No buy candidates available."
        )

except Exception as e:

    st.warning(
        f"Unable to load buy candidates:\n{e}"
    )

# ==========================================
# Footer
# ==========================================

st.divider()

st.caption(
    "Investment Advisor • Massive Market Data • SEC Fundamentals • Robinhood Portfolio Tracking"
)
