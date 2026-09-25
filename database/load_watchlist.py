import sqlite3

conn = sqlite3.connect("InvestmentAdvisor.db")
cursor = conn.cursor()

watchlist = [
    "AAPL",
    "MSFT",
    "NVDA",
    "GOOGL",
    "AMZN",
    "META",
    "TSLA"
]

for ticker in watchlist:

    cursor.execute("""
    INSERT OR IGNORE INTO watchlist
    (ticker)
    VALUES (?)
    """,
    (ticker,)
    )

conn.commit()

print("Watchlist Loaded Successfully")

conn.close()
