import sqlite3

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS company_universe (

    ticker TEXT PRIMARY KEY,

    company_name TEXT,

    sector TEXT,

    industry TEXT,

    source TEXT,

    date_added TEXT DEFAULT CURRENT_TIMESTAMP

)
""")

conn.commit()

conn.close()

print(
    "\ncompany_universe created successfully."
)
