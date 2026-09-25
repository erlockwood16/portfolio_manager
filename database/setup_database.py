import sqlite3

# Create database
conn = sqlite3.connect("InvestmentAdvisor.db")

# Create cursor
cursor = conn.cursor()

# Create stocks table
cursor.execute("""
CREATE TABLE IF NOT EXISTS stocks (
    ticker TEXT PRIMARY KEY,
    company_name TEXT,
    sector TEXT,
    industry TEXT
)
""")

conn.commit()

print("Database Created Successfully")

conn.close()