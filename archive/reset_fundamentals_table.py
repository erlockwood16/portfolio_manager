import sqlite3

conn = sqlite3.connect("InvestmentAdvisor.db")
cursor = conn.cursor()

cursor.execute("""
DROP TABLE IF EXISTS fundamentals
""")

cursor.execute("""
CREATE TABLE fundamentals (

    ticker TEXT PRIMARY KEY,

    market_cap REAL,

    pe_ratio REAL,

    eps REAL,

    revenue_growth REAL,

    earnings_growth REAL,

    debt_to_equity REAL,

    roe REAL,

    free_cash_flow REAL,

    book_value_per_share REAL,

    price_to_book REAL,

    last_updated TEXT

)
""")

conn.commit()

print("Fundamentals table recreated")

conn.close()
