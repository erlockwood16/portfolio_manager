import sqlite3

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

ticker = input(
    "Ticker: "
).upper()

cursor.execute("""
SELECT
    fiscal_year,
    revenue,
    net_income,
    assets,
    liabilities
FROM sec_financials
WHERE ticker = ?
ORDER BY fiscal_year DESC
""",
(ticker,)
)

rows = cursor.fetchall()

print()

for row in rows:

    print(
        f"FY{row[0]} | "
        f"Revenue={row[1]} | "
        f"NetIncome={row[2]}"
    )

conn.close()
