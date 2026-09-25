import sqlite3

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

cursor.execute("""
SELECT *
FROM sec_financials
ORDER BY ticker
""")

rows = cursor.fetchall()

print("\nSEC FINANCIALS\n")

for row in rows:

    print(
        f"{row[0]} | "
        f"FY{row[1]} | "
        f"Revenue={row[2]} | "
        f"NetIncome={row[3]}"
    )

conn.close()
