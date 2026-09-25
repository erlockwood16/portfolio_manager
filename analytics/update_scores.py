import sqlite3
import pandas as pd
import numpy as np

from datetime import datetime

# ========================================
# Connect Database
# ========================================

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

query = """
SELECT
    ticker,
    price_date,
    close_price
FROM prices
ORDER BY ticker, price_date
"""

df = pd.read_sql(query, conn)

cursor = conn.cursor()

score_date = datetime.today().strftime(
    "%Y-%m-%d"
)

processed = 0

# ========================================
# Calculate Scores
# ========================================

for ticker in df["ticker"].unique():

    stock = (
        df[df["ticker"] == ticker]
        .sort_values("price_date")
        .copy()
    )

    # Need enough data for SMA200

    if len(stock) < 200:

        print(
            f"Skipping {ticker} "
            f"(only {len(stock)} records)"
        )

        continue

    current_price = float(
        stock.iloc[-1]["close_price"]
    )

    sma20 = float(
        stock["close_price"]
        .rolling(20)
        .mean()
        .iloc[-1]
    )

    sma50 = float(
        stock["close_price"]
        .rolling(50)
        .mean()
        .iloc[-1]
    )

    sma200 = float(
        stock["close_price"]
        .rolling(200)
        .mean()
        .iloc[-1]
    )

    # ========================================
    # Momentum Score
    # ========================================

    momentum_score = 0

    if current_price > sma20:
        momentum_score += 30

    if current_price > sma50:
        momentum_score += 30

    if current_price > sma200:
        momentum_score += 40

    # ========================================
    # Volatility
    # ========================================

    stock["returns"] = (
        stock["close_price"]
        .pct_change()
    )

    volatility = (
        stock["returns"]
        .std()
        * np.sqrt(252)
        * 100
    )

    volatility = round(
        float(volatility),
        2
    )

    # ========================================
    # Overall Score
    # ========================================

    overall_score = round(
        momentum_score
        - (volatility * 0.5),
        2
    )

    # ========================================
    # Save Results
    # ========================================

    cursor.execute("""
    INSERT OR REPLACE INTO analytics_scores
    (
        ticker,
        current_price,
        sma20,
        sma50,
        sma200,
        momentum_score,
        volatility,
        overall_score,
        score_date
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
    (
        ticker,
        current_price,
        sma20,
        sma50,
        sma200,
        momentum_score,
        volatility,
        overall_score,
        score_date
    ))

    processed += 1

    print(
        f"{ticker} | "
        f"Momentum={momentum_score} | "
        f"Vol={volatility:.2f} | "
        f"Overall={overall_score:.2f}"
    )

conn.commit()

print(
    f"\n{processed} tickers scored"
)

conn.close()
