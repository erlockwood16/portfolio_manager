# fundamentals/check_fundamentals_schema.py

import sqlite3

conn = sqlite3.connect("InvestmentAdvisor.db")
cursor = conn.cursor()

cursor.execute("""
PRAGMA table_info(fundamentals)
""")

for row in cursor.fetchall():
    print(row)

conn.close()
