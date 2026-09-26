import sqlite3

conn = sqlite3.connect("InvestmentAdvisor.db")
cursor = conn.cursor()

cursor.execute("""
SELECT
    ticker,
    overall_score
FROM screen_scores
WHERE overall_score > 105
ORDER BY overall_score DESC
""")

rows = cursor.fetchall()

print("\nBUY CANDIDATES\n")

for row in rows:

    ticker = row[0]
    score = row[1]

    print(
        f"{ticker} "
        f"Score={score:.1f}"
    )

conn.close()