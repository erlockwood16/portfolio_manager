import json
import sqlite3

DB_PATH = "InvestmentAdvisor.db"

with open(
    "data/company_tickers.json",
    "r",
    encoding="utf-8"
) as f:

    data = json.load(f)

conn = sqlite3.connect(DB_PATH)

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS sec_company_map (

    ticker TEXT PRIMARY KEY,

    cik TEXT,

    company_name TEXT

)
""")

count = 0

for record in data.values():

    ticker = record["ticker"]

    cik = str(
        record["cik_str"]
    ).zfill(10)

    company_name = record["title"]

    cursor.execute("""
    INSERT OR REPLACE INTO sec_company_map (
        ticker,
        cik,
        company_name
    )
    VALUES (?, ?, ?)
    """,
    (
        ticker,
        cik,
        company_name
    ))

    count += 1

conn.commit()

conn.close()

print(
    f"Loaded {count:,} SEC mappings"
)
