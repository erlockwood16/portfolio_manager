import sqlite3

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

companies = [

    ("AAPL", "0000320193"),
    ("MSFT", "0000789019"),
    ("GOOGL", "0001652044"),
    ("NVDA", "0001045810"),
    ("TSLA", "0001318605")

]

for company in companies:

    cursor.execute("""
    INSERT OR REPLACE INTO sec_company_map
    (
        ticker,
        cik
    )
    VALUES (?, ?)
    """,
    company
    )

conn.commit()

conn.close()

print(
    "Company Map Loaded"
)
