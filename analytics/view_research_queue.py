import sqlite3

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

cursor.execute("""
SELECT
    ticker,
    overall_score,
    recommendation,
    added_date,
    status
FROM research_queue
ORDER BY overall_score DESC
""")

rows = cursor.fetchall()

print("\nRESEARCH QUEUE\n")

for row in rows:

    print(
        f"{row[0]:<8} "
        f"Score={row[1]:>6.2f}  "
        f"{row[2]:<12} "
        f"Status={row[4]}"
    )

conn.close()
