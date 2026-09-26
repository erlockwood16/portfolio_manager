import sqlite3

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

cursor.execute("""
DROP TABLE IF EXISTS sec_financials
""")

cursor.execute("""
CREATE TABLE sec_financials (

    ticker TEXT,

    fiscal_year INTEGER,

    revenue REAL,

    net_income REAL,

    assets REAL,

    liabilities REAL,

    PRIMARY KEY (
        ticker,
        fiscal_year
    )

)
""")

conn.commit()

print(
    "sec_financials recreated"
)

conn.close()
