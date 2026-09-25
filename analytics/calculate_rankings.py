import sqlite3
import pandas as pd
from datetime import datetime

conn = sqlite3.connect("InvestmentAdvisor.db")

query = """
SELECT
    ticker,
    price_date,
    close_price
FROM prices
"""

df = pd.read_sql(query, conn)

cursor = conn.cursor()

for ticker in df["ticker"].unique():

    stock = (
        df[df["ticker"] == ticker]
        .sort_values("price_date")
    )

    if len(stock) < 20:
        continue

    current_price = stock.iloc[-1]["close_price"]

    sma20 = (
        stock["close_price"]
        .tail(20)
        .mean()
    )

    momentum_score = (
        current_price / sma20
    ) * 100

    overall_score = momentum_score

    cursor.execute("""
    INSERT OR REPLACE INTO screen_scores
    (
        ticker,
        momentum_score,
        overall_score,
        last_updated
    )
    VALUES (?, ?, ?, ?)
    """,
    (
        ticker,
        momentum_score,
        overall_score,
        datetime.today().strftime("%Y-%m-%d")
    ))

conn.commit()

print("Scores Updated")

conn.close()
