import sqlite3
import pandas as pd

conn = sqlite3.connect("InvestmentAdvisor.db")

query = """
SELECT
    ticker,
    price_date,
    close_price
FROM prices
ORDER BY ticker, price_date
"""

df = pd.read_sql(query, conn)

results = []

for ticker in df["ticker"].unique():

    stock = (
        df[df["ticker"] == ticker]
        .sort_values("price_date")
    )

    if len(stock) < 200:
        continue

    current_price = stock.iloc[-1]["close_price"]

    sma20 = stock["close_price"].rolling(20).mean().iloc[-1]
    sma50 = stock["close_price"].rolling(50).mean().iloc[-1]
    sma200 = stock["close_price"].rolling(200).mean().iloc[-1]

    momentum_score = 0

    if current_price > sma20:
        momentum_score += 30

    if current_price > sma50:
        momentum_score += 30

    if current_price > sma200:
        momentum_score += 40

    results.append([
        ticker,
        current_price,
        sma20,
        sma50,
        sma200,
        momentum_score
    ])

scores = pd.DataFrame(
    results,
    columns=[
        "ticker",
        "current_price",
        "sma20",
        "sma50",
        "sma200",
        "momentum_score"
    ]
)

print(scores)

conn.close()
