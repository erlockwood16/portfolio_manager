import sqlite3

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

cursor.execute("""
SELECT
    ticker,
    current_price,
    overall_score,
    recommendation,
    run_date
FROM buy_candidates
ORDER BY overall_score DESC
""")

rows = cursor.fetchall()

print("\nBUY CANDIDATES\n")

for row in rows:

    print(
        f"{row[0]:<8}"
        f"Price=${row[1]:>8.2f}  "
        f"Score={row[2]:>6.2f}  "
        f"{row[3]:<12} "
        f"{row[4]}"
    )

conn.close()
