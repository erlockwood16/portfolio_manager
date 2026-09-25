import sqlite3

# ==========================================
# Connect Database
# ==========================================

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

# ==========================================
# Create Watchlist Table
# ==========================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS watchlist (

    ticker TEXT PRIMARY KEY

)
""")

conn.commit()

conn.close()

print(
    "\nWatchlist table created successfully."
)
