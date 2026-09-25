import sqlite3

conn = sqlite3.connect("InvestmentAdvisor.db")
cursor = conn.cursor()

cursor.execute("""
SELECT *
FROM watchlist
ORDER BY ticker
""")

rows = cursor.fetchall()

for row in rows:
    print(row)

conn.close()