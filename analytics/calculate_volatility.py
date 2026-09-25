import sqlite3
import pandas as pd
import numpy as np

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

    if len(stock) < 30:
        continue

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

    results.append([
        ticker,
        round(volatility, 2)
    ])

vol_df = pd.DataFrame(
    results,
    columns=[
        "ticker",
        "volatility"
    ]
)

print(vol_df)

conn.close()
