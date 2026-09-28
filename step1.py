import sqlite3

conn = sqlite3.connect("InvestmentAdvisor.db")

print(
    conn.execute(
        "SELECT COUNT(*) FROM sec_company_map"
    ).fetchone()[0]
)

conn.close()
