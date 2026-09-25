import sqlite3

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

cursor.execute("""
SELECT *
FROM backfill_status
ORDER BY ticker
""")

rows = cursor.fetchall()

print()

for row in rows:

    print(row)

conn.close()
