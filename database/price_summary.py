import sqlite3

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

cursor.execute("""
SELECT
    ticker,
    COUNT(*) AS row_count,
    MIN(price_date),
    MAX(price_date)
FROM prices
GROUP BY ticker
ORDER BY ticker
""")

rows = cursor.fetchall()

print()

for row in rows:

    print(
        f"{row[0]} | "
        f"{row[1]} rows | "
        f"{row[2]} -> {row[3]}"
    )

conn.close()
