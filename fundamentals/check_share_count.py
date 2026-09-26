# fundamentals/check_share_count.py

import sqlite3

conn = sqlite3.connect("InvestmentAdvisor.db")
cursor = conn.cursor()

cursor.execute("""
SELECT COUNT(*)
FROM sec_financials
WHERE shares_outstanding IS NOT NULL
""")

print(cursor.fetchone())

conn.close()
