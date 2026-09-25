import sqlite3

conn = sqlite3.connect("InvestmentAdvisor.db")
cursor = conn.cursor()

cursor.execute("""
SELECT
    ticker,
    price_date,
    close_price,
    volume
FROM prices
ORDER BY ticker
""")

rows = cursor.fetchall()

for row in rows:
    print(row)

conn.close()
