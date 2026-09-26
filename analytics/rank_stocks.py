import sqlite3

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

cursor.execute("""
SELECT
    ticker,
    current_price,
    momentum_score,
    volatility,
    overall_score
FROM analytics_scores
ORDER BY overall_score DESC
""")

rows = cursor.fetchall()

print("\nSTOCK RANKINGS\n")

rank = 1

for row in rows:

    print(
        f"{rank}. "
        f"{row[0]} | "
        f"Score={row[4]:.2f} | "
        f"Momentum={row[2]:.2f} | "
        f"Vol={row[3]:.2f}"
    )

    rank += 1

conn.close()