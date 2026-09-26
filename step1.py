import sqlite3

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

cursor.execute("""
SELECT
    cash_type,
    ROUND(SUM(amount),2)
FROM robinhood_cash_ledger
GROUP BY cash_type
ORDER BY cash_type
""")

for row in cursor.fetchall():
    print(row)

conn.close()
