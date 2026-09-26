import sqlite3
from datetime import datetime

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

data = [

    (
        "MSFT",
        3800,
        35,
        13,
        15,
        0.35,
        32,
        74000000000
    ),

    (
        "AAPL",
        3200,
        31,
        8,
        10,
        1.40,
        145,
        100000000000
    ),

    (
        "GOOGL",
        2500,
        25,
        12,
        14,
        0.10,
        28,
        75000000000
    )

]

for row in data:

    cursor.execute("""
    INSERT OR REPLACE INTO fundamentals
    (
        ticker,
        market_cap,
        pe_ratio,
        revenue_growth,
        earnings_growth,
        debt_to_equity,
        roe,
        free_cash_flow,
        last_updated
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
    (
        row[0],
        row[1],
        row[2],
        row[3],
        row[4],
        row[5],
        row[6],
        row[7],
        datetime.today().strftime(
            "%Y-%m-%d"
        )
    ))

conn.commit()

conn.close()

print(
    "Fundamentals Loaded"
)
