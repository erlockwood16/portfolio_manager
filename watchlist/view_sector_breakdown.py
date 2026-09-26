import sqlite3

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

cursor.execute("""
SELECT

    sector,

    COUNT(*)

FROM company_universe

GROUP BY sector

ORDER BY COUNT(*) DESC
""")

print(
    "\nS&P 500 SECTOR BREAKDOWN\n"
)

for sector, count in cursor.fetchall():

    print(
        f"{sector:<30}"
        f"{count}"
    )

conn.close()
