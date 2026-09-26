import sqlite3

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

cursor.execute("""
SELECT *
FROM update_status
ORDER BY ticker
""")

rows = cursor.fetchall()

print("\nUPDATE STATUS\n")

for row in rows:

    print(
        f"{row[0]} "
        f"last updated "
        f"{row[1]}"
    )

conn.close()
