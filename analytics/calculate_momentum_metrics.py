import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime

# ==========================================
# Database
# ==========================================

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

# ==========================================
# Create Table
# ==========================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS momentum_metrics (

    ticker TEXT PRIMARY KEY,

    return_1m REAL,

    return_3m REAL,

    return_6m REAL,

    return_12m REAL,

    pct_from_52w_high REAL,

    pct_from_52w_low REAL,

    momentum_score REAL,

    calculated_date TEXT

)
""")

# ==========================================
# Load Price History
# ==========================================

query = """
SELECT

    ticker,

    price_date,

    close_price

FROM prices

ORDER BY
    ticker,
    price_date
"""

df = pd.read_sql_query(
    query,
    conn
)

if df.empty:

    print(
        "\nNo price history found."
    )

    conn.close()

    raise SystemExit

df["price_date"] = pd.to_datetime(
    df["price_date"]
)

# ==========================================
# Calculate Metrics
# ==========================================

results = []

for ticker, group in df.groupby("ticker"):

    group = (

        group
        .sort_values("price_date")
        .reset_index(drop=True)

    )

    if len(group) < 252:

        continue

    latest_price = (
        group.iloc[-1]["close_price"]
    )

    # --------------------------------------
    # Returns
    # --------------------------------------

    def calc_return(period):

        if len(group) <= period:

            return None

        old_price = (
            group.iloc[-period]["close_price"]
        )

        if old_price == 0:

            return None

        return round(

            (
                (
                    latest_price
                    -
                    old_price
                )
                /
                old_price
            )

            * 100,

            2

        )

    return_1m = calc_return(21)

    return_3m = calc_return(63)

    return_6m = calc_return(126)

    return_12m = calc_return(252)

    # --------------------------------------
    # 52 Week Range
    # --------------------------------------

    trailing_year = group.tail(252)

    high_52w = (
        trailing_year["close_price"]
        .max()
    )

    low_52w = (
        trailing_year["close_price"]
        .min()
    )

    pct_from_52w_high = round(

        (
            (
                latest_price
                -
                high_52w
            )
            /
            high_52w
        )

        * 100,

        2

    )

    pct_from_52w_low = round(

        (
            (
                latest_price
                -
                low_52w
            )
            /
            low_52w
        )

        * 100,

        2

    )

    # --------------------------------------
    # Momentum Score
    # --------------------------------------

    scores = []

    for value in [

        return_1m,

        return_3m,

        return_6m,

        return_12m

    ]:

        if value is not None:

            scores.append(

                max(
                    0,
                    min(
                        100,
                        value + 50
                    )
                )

            )

    momentum_score = None

    if scores:

        momentum_score = round(

            np.mean(scores),

            2

        )

    results.append(

        (

            ticker,

            return_1m,

            return_3m,

            return_6m,

            return_12m,

            pct_from_52w_high,

            pct_from_52w_low,

            momentum_score,

            datetime.today().strftime(
                "%Y-%m-%d"
            )

        )

    )

# ==========================================
# Save Results
# ==========================================

cursor.executemany("""
INSERT OR REPLACE
INTO momentum_metrics
(

    ticker,

    return_1m,

    return_3m,

    return_6m,

    return_12m,

    pct_from_52w_high,

    pct_from_52w_low,

    momentum_score,

    calculated_date

)
VALUES
(
    ?, ?, ?, ?, ?, ?, ?, ?, ?
)
""",
results
)

conn.commit()

# ==========================================
# Summary
# ==========================================

cursor.execute("""
SELECT COUNT(*)
FROM momentum_metrics
""")

count = cursor.fetchone()[0]

conn.close()

print("\n" + "=" * 70)

print(
    "MOMENTUM METRICS COMPLETE"
)

print("=" * 70)

print(
    f"\nTickers Processed: {count}"
)

print("=" * 70)
