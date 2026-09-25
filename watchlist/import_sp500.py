import sqlite3
import pandas as pd
from pathlib import Path

# ==========================================
# Configuration
# ==========================================

DB_PATH = "InvestmentAdvisor.db"

CSV_PATH = Path("data/sp500.csv")

# ==========================================
# Verify File Exists
# ==========================================

if not CSV_PATH.exists():

    raise FileNotFoundError(
        f"File not found: {CSV_PATH}"
    )

# ==========================================
# Load CSV
# ==========================================

sp500 = pd.read_csv(
    CSV_PATH
)

# ==========================================
# Verify Column Exists
# ==========================================

if "Symbol" not in sp500.columns:

    raise ValueError(
        "\nColumn 'Symbol' not found.\n\n"
        f"Available columns:\n"
        f"{list(sp500.columns)}"
    )

# ==========================================
# Build Ticker List
# ==========================================

tickers = (

    sp500["Symbol"]

    .dropna()

    .astype(str)

    .str.strip()

    .str.replace(
        ".",
        "-",
        regex=False
    )

    .tolist()

)

print(
    f"\nLoaded "
    f"{len(tickers)} "
    f"tickers from CSV"
)

# ==========================================
# Database
# ==========================================

conn = sqlite3.connect(
    DB_PATH
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

# ==========================================
# Import Tickers
# ==========================================

added = 0

for ticker in tickers:

    cursor.execute("""
    INSERT OR IGNORE INTO watchlist
    (
        ticker
    )
    VALUES
    (
        ?
    )
    """,
    (
        ticker,
    ))

    added += cursor.rowcount

conn.commit()

# ==========================================
# Verification
# ==========================================

cursor.execute("""
SELECT COUNT(*)
FROM watchlist
""")

total = cursor.fetchone()[0]

print("\n" + "=" * 60)
print("S&P 500 IMPORT COMPLETE")
print("=" * 60)

print(
    f"\nNew Tickers Added: "
    f"{added}"
)

print(
    f"Total Watchlist Size: "
    f"{total}"
)

# Sample tickers

cursor.execute("""
SELECT ticker
FROM watchlist
ORDER BY ticker
LIMIT 20
""")

print("\nSample Tickers\n")

for row in cursor.fetchall():

    print(row[0])

conn.close()
