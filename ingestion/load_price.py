import os
import sqlite3
import requests

from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

API_KEY = os.getenv("MASSIVE_API_KEY")

if not API_KEY:
    raise ValueError(
        "MASSIVE_API_KEY not found in .env file"
    )

# Connect database
conn = sqlite3.connect("InvestmentAdvisor.db")
cursor = conn.cursor()

# Get watchlist
cursor.execute("""
SELECT ticker
FROM watchlist
ORDER BY ticker
""")

tickers = [row[0] for row in cursor.fetchall()]

print(f"Loading {len(tickers)} tickers...")

for ticker in tickers:

    print(f"\nLoading {ticker}...")

    try:

        url = (
            f"https://api.massive.com/v2/aggs/ticker/"
            f"{ticker}/prev?apiKey={API_KEY}"
        )

        response = requests.get(url)

        if response.status_code != 200:

            print(
                f"Failed: {ticker}"
            )

            continue

        data = response.json()

        if "results" not in data:

            print(
                f"No data for {ticker}"
            )

            continue

        result = data["results"][0]

        open_price = result["o"]
        high_price = result["h"]
        low_price = result["l"]
        close_price = result["c"]
        volume = result["v"]

        timestamp = result["t"]

        price_date = datetime.utcfromtimestamp(
            timestamp / 1000
        ).strftime("%Y-%m-%d")

        cursor.execute("""
        INSERT OR REPLACE INTO prices (
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
            open_price,
            high_price,
            low_price,
            close_price,
            volume
        ))

        print(
            f"{ticker} | "
            f"{price_date} | "
            f"Close = {close_price}"
        )

    except Exception as e:

        print(
            f"Error loading {ticker}: {e}"
        )

conn.commit()
conn.close()

print("\nAll Price Data Loaded.")