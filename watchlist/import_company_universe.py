import sqlite3
import pandas as pd

from pathlib import Path

# ==========================================
# Configuration
# ==========================================

CSV_PATH = Path(
    "data/sp500.csv"
)

# ==========================================
# Verify File Exists
# ==========================================

if not CSV_PATH.exists():

    raise FileNotFoundError(
        f"Missing file: {CSV_PATH}"
    )

# ==========================================
# Load CSV
# ==========================================

df = pd.read_csv(
    CSV_PATH
)

required_columns = [

    "Symbol",

    "Security",

    "GICS Sector",

    "GICS Sub-Industry"

]

missing = [

    col

    for col in required_columns

    if col not in df.columns

]

if missing:

    raise ValueError(
        f"Missing columns: {missing}"
    )

# ==========================================
# Database
# ==========================================

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

inserted = 0

# ==========================================
# Import
# ==========================================

for _, row in df.iterrows():

    ticker = (

        str(
            row["Symbol"]
        )

        .strip()

        .replace(
            ".",
            "-"
        )

    )

    company_name = str(
        row["Security"]
    ).strip()

    sector = str(
        row["GICS Sector"]
    ).strip()

    industry = str(
        row["GICS Sub-Industry"]
    ).strip()

    cursor.execute("""
    INSERT OR REPLACE
    INTO company_universe
    (

        ticker,

        company_name,

        sector,

        industry,

        source

    )
    VALUES
    (
        ?, ?, ?, ?, ?
    )
    """,
    (

        ticker,

        company_name,

        sector,

        industry,

        "SP500"

    ))

    inserted += 1

conn.commit()

# ==========================================
# Summary
# ==========================================

cursor.execute("""
SELECT COUNT(*)
FROM company_universe
""")

total = cursor.fetchone()[0]

conn.close()

print("\n" + "=" * 60)

print(
    "COMPANY UNIVERSE IMPORT COMPLETE"
)

print("=" * 60)

print(
    f"\nImported: {inserted}"
)

print(
    f"Universe Size: {total}"
)
