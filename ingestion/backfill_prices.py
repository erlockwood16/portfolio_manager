import os
import sqlite3
import requests

from dotenv import load_dotenv
from datetime import datetime

# -----------------------------------
# Configuration
# -----------------------------------

START_DATE = "2025-01-01"

# -----------------------------------
# Load API Key
# -----------------------------------

load_dotenv()

API_KEY = os.getenv("MASSIVE_API_KEY")

if not API_KEY:
    raise ValueError(
        "MASSIVE_API_KEY not found in .env file"
    )

# -----------------------------------
# Database
# -----------------------------------

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

# -----------------------------------
# Get Watchlist
# -----------------------------------

cursor.execute("""
SELECT ticker
FROM watchlist
ORDER BY ticker
""")

tickers = [
    row[0]
    for row in cursor.fetchall()
]

print(
    f"\nFound {len(tickers)} watchlist tickers"
)

# -----------------------------------
# Process Each Ticker
# -----------------------------------

for ticker in tickers:

    # Check if already backfilled

    cursor.execute("""
    SELECT historical_loaded
    FROM backfill_status
    WHERE ticker = ?
    """,
    (ticker,)
    )

    result = cursor.fetchone()

    if result and result[0] == "Y":

        print(
            f"{ticker} already backfilled - skipping"
        )

        continue

    print(
        f"\nBackfilling {ticker}"
    )

    end_date = datetime.today().strftime(
        "%Y-%m-%d"
    )

    url = (
        f"https://api.massive.com/v2/aggs/ticker/"
        f"{ticker}/range/1/day/"
        f"{START_DATE}/{end_date}"
        f"?adjusted=true"
        f"&sort=asc"
        f"&limit=5000"
        f"&apiKey={API_KEY}"
    )

    try:

        response = requests.get(
            url,
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        if "results" not in data:

            print(
                f"No history returned for {ticker}"
            )

            continue

        bars = data["results"]

        rows_loaded = 0

        for bar in bars:

            price_date = datetime.utcfromtimestamp(
                bar["t"] / 1000
            ).strftime("%Y-%m-%d")

            cursor.execute("""
            INSERT OR REPLACE INTO prices
            (
                ticker,
                price_date,
                open_price,
                high_price,
                low_price,
                close_price,
                volume
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticker,
                price_date,
                bar["o"],
                bar["h"],
                bar["l"],
                bar["c"],
                bar["v"]
            ))

            rows_loaded += 1

        # Mark ticker as completed

        cursor.execute("""
        INSERT OR REPLACE INTO backfill_status
        (
            ticker,
            historical_loaded,
            load_date,
            rows_loaded
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            ticker,
            "Y",
            datetime.today().strftime(
                "%Y-%m-%d"
            ),
            rows_loaded
        ))

        conn.commit()

        print(
            f"{ticker} loaded "
            f"({rows_loaded} records)"
        )

    except Exception as e:

        print(
            f"Error loading {ticker}"
        )

        print(e)

conn.close()

print(
    "\nHistorical Backfill Complete"
)