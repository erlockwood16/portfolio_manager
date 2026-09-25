import sqlite3

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

cursor.execute("""
SELECT ticker
FROM watchlist
ORDER BY ticker
LIMIT 25
""")

for row in cursor.fetchall():

    print(row[0])

conn.close()