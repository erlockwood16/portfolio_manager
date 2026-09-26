# fundamentals/check_shares.py

import sqlite3

conn = sqlite3.connect("InvestmentAdvisor.db")
cursor = conn.cursor()

cursor.execute("""
SELECT
    ticker,
    fiscal_year,
    shares_outstanding
FROM sec_financials
ORDER BY ticker,
         fiscal_year DESC
""")

rows = cursor.fetchall()

for row in rows:
    print(row)

conn.close()
