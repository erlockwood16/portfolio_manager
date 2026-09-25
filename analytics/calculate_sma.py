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

    results.append([
        ticker,
        current_price,
        sma20,
        sma50,
        sma200
    ])

results_df = pd.DataFrame(
    results,
    columns=[
        "ticker",
        "current_price",
        "sma20",
        "sma50",
        "sma200"
    ]
)

print(results_df)

conn.close()
