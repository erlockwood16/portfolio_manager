# database/check_analytics_schema.py

import sqlite3

conn = sqlite3.connect("InvestmentAdvisor.db")
cursor = conn.cursor()

cursor.execute("""
PRAGMA table_info(analytics_scores)
""")

for row in cursor.fetchall():
    print(row)

conn.close()
