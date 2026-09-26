import sqlite3

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

ticker = input(
    "Enter ticker: "
).upper()

cursor.execute("""
SELECT memo_text
FROM research_memos
WHERE ticker = ?
""",
(ticker,)
)

row = cursor.fetchone()

if row:

    print(row[0])

else:

    print(
        f"No memo found for {ticker}"
    )

conn.close()