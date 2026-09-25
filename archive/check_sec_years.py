# fundamentals/check_sec_years.py

import sqlite3

conn = sqlite3.connect("InvestmentAdvisor.db")
cursor = conn.cursor()

cursor.execute("""
SELECT
    ticker,
    fiscal_year
FROM sec_financials
ORDER BY ticker, fiscal_year DESC
""")

for row in cursor.fetchall():
    print(row)

conn.close()
