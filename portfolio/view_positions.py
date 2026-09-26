import sqlite3

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

cursor.execute("""
SELECT

    ticker,

    shares,

    average_cost,

    total_cost_basis

FROM portfolio_positions

ORDER BY ticker
""")

rows = cursor.fetchall()

print("\nCURRENT POSITIONS\n")

for row in rows:

    ticker, shares, average_cost, total_cost_basis = row

    print(
        f"{ticker:<8}"
        f"Shares={shares:10.4f}"
        f"Avg Cost=${average_cost:10.2f}"
        f"Cost Basis=${total_cost_basis:12.2f}"
    )

conn.close()
