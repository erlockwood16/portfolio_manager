import sqlite3
import pandas as pd

from datetime import datetime

# ==========================================
# CONFIGURATION
# ==========================================

DB_PATH = "InvestmentAdvisor.db"

# ==========================================
# Database
# ==========================================

conn = sqlite3.connect(DB_PATH)

cursor = conn.cursor()

# ==========================================
# Cash Balance
# ==========================================

def get_actual_cash_balance(conn):

    cursor = conn.cursor()

    cursor.execute("""
    SELECT cash_balance
    FROM portfolio_cash
    WHERE source='ROBINHOOD'
    """)

    row = cursor.fetchone()

    imported_cash = row[0] if row else 0

    cursor.execute("""
    SELECT
        COALESCE(
            SUM(amount),
            0
        )
    FROM cash_adjustments
    """)

    adjustments = cursor.fetchone()[0]

    return round(
        imported_cash + adjustments,
        2
    )

# ==========================================
# Snapshot Table
# ==========================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS portfolio_snapshots (

    snapshot_date TEXT PRIMARY KEY,

    total_positions INTEGER,

    portfolio_market_value REAL,

    cash_balance REAL,

    total_account_value REAL,

    portfolio_cost_basis REAL,

    unrealized_gain_loss REAL,

    return_pct REAL,

    created_timestamp TEXT

)
""")

conn.commit()

# ==========================================
# Latest Prices
# ==========================================

query = """
WITH latest_prices AS (

    SELECT

        ticker,

        close_price

    FROM (

        SELECT

            ticker,

            close_price,

            ROW_NUMBER() OVER (

                PARTITION BY ticker

                ORDER BY
                    price_date DESC,
                    rowid DESC

            ) AS rn

        FROM prices

    )

    WHERE rn = 1

)

SELECT

    pp.ticker,

    pp.shares,

    pp.average_cost,

    lp.close_price

FROM portfolio_positions pp

LEFT JOIN latest_prices lp
       ON pp.ticker = lp.ticker

WHERE
    UPPER(
        COALESCE(
            pp.source,
            ''
        )
    ) = 'ROBINHOOD'
"""

df = pd.read_sql_query(
    query,
    conn
)

# ==========================================
# Empty Portfolio
# ==========================================

if df.empty:

    print(
        "\nNo portfolio positions found."
    )

    conn.close()

    raise SystemExit

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

portfolio_market_value = round(
    df["market_value"].sum(),
    2
)

portfolio_cost_basis = round(
    df["cost_basis"].sum(),
    2
)

cash_balance = get_actual_cash_balance(conn)

total_account_value = round(
    portfolio_market_value
    +
    cash_balance,
    2
)

unrealized_gain_loss = round(
    portfolio_market_value
    -
    portfolio_cost_basis,
    2
)

return_pct = 0

if portfolio_cost_basis > 0:

    return_pct = round(
        (
            unrealized_gain_loss
            /
            portfolio_cost_basis
        )
        * 100,
        2
    )

# ==========================================
# Snapshot Metadata
# ==========================================

snapshot_date = datetime.today().strftime(
    "%Y-%m-%d"
)

created_timestamp = datetime.now().strftime(
    "%Y-%m-%d %H:%M:%S"
)

# ==========================================
# Save Snapshot
# ==========================================

cursor.execute("""
INSERT OR REPLACE
INTO portfolio_snapshots
(

    snapshot_date,

    total_positions,

    portfolio_market_value,

    cash_balance,

    total_account_value,

    portfolio_cost_basis,

    unrealized_gain_loss,

    return_pct,

    created_timestamp

)
VALUES
(
    ?, ?, ?, ?, ?, ?, ?, ?, ?
)
""",
(
    snapshot_date,

    len(df),

    portfolio_market_value,

    cash_balance,

    total_account_value,

    portfolio_cost_basis,

    unrealized_gain_loss,

    return_pct,

    created_timestamp

))

conn.commit()

# ==========================================
# Count Snapshots
# ==========================================

cursor.execute("""
SELECT COUNT(*)
FROM portfolio_snapshots
""")

snapshot_count = cursor.fetchone()[0]

conn.close()

# ==========================================
# Summary
# ==========================================

print("\n" + "=" * 70)

print(
    "PORTFOLIO SNAPSHOT CAPTURED"
)

print("=" * 70)

print(
    f"\nDate               : "
    f"{snapshot_date}"
)

print(
    f"Positions          : "
    f"{len(df)}"
)

print(
    f"Market Value       : "
    f"${portfolio_market_value:,.2f}"
)

print(
    f"Cash Balance       : "
    f"${cash_balance:,.2f}"
)

print(
    f"Total Account Value: "
    f"${total_account_value:,.2f}"
)

print(
    f"Cost Basis         : "
    f"${portfolio_cost_basis:,.2f}"
)

print(
    f"Gain / Loss        : "
    f"${unrealized_gain_loss:,.2f}"
)

print(
    f"Return             : "
    f"{return_pct:.2f}%"
)

print(
    f"Snapshots Stored   : "
    f"{snapshot_count}"
)

print("=" * 70)
