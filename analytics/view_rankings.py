import sqlite3

conn = sqlite3.connect("InvestmentAdvisor.db")
cursor = conn.cursor()

cursor.execute("""
SELECT
    ticker,
    overall_score
FROM screen_scores
ORDER BY overall_score DESC
""")

rows = cursor.fetchall()

for row in rows:
    print(row)

conn.close()
