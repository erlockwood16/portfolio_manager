# database/reset_analytics_table.py

import sqlite3

conn = sqlite3.connect("InvestmentAdvisor.db")
cursor = conn.cursor()

cursor.execute("""
DROP TABLE IF EXISTS analytics_scores
""")

cursor.execute("""
CREATE TABLE analytics_scores (
    ticker TEXT PRIMARY KEY,
    current_price REAL,
    sma20 REAL,
    sma50 REAL,
    sma200 REAL,
    momentum_score REAL,
    volatility REAL,
    overall_score REAL,
    score_date TEXT
)
""")

conn.commit()

print("analytics_scores recreated")

conn.close()
