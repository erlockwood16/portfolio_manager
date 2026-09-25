import sqlite3
import yfinance as yf
import pandas as pd

from datetime import datetime

# ==========================================
# Configuration
# ==========================================

BATCH_SIZE = 100

# ==========================================
# Database
# ==========================================

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

today = datetime.today().strftime(
    "%Y-%m-%d"
)

# ==========================================
# Load Watchlist
# ==========================================

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
    f"\nProcessing "
    f"{len(tickers)} tickers"
)

# ==========================================
# Batch Download
# ==========================================

for start in range(
    0,
    len(tickers),
    BATCH_SIZE
):

    batch = tickers[
        start:
        start + BATCH_SIZE
    ]

    print(
        f"\nDownloading "
        f"{len(batch)} tickers "
        f"({start + 1} - "
        f"{min(start + BATCH_SIZE, len(tickers))})"
    )

    try:

        data = yf.download(

            tickers=batch,

            period="5d",

            auto_adjust=False,

            progress=False,

            group_by="ticker",

            threads=True

        )

        # ----------------------------------
        # Process Each Ticker
        # ----------------------------------

        for ticker in batch:

            try:

                if ticker not in data:

                    print(
                        f"No data: {ticker}"
                    )

                    continue

                df = data[ticker]

                if df.empty:

                    print(
                        f"Empty: {ticker}"
                    )

                    continue

                latest = df.iloc[-1]

                price_date = df.index[-1].strftime(
                    "%Y-%m-%d"
                )

                cursor.execute("""
                INSERT OR REPLACE
                INTO prices
                (
                    ticker,
                    price_date,
                    open_price,
                    high_price,
                    low_price,
                    close_price,
                    volume
                )
                VALUES
                (
                    ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    ticker,
                    price_date,

                    float(latest["Open"]),
                    float(latest["High"]),
                    float(latest["Low"]),
                    float(latest["Close"]),
                    int(latest["Volume"])
                ))

                cursor.execute("""
                INSERT OR REPLACE
                INTO update_status
                (
                    ticker,
                    last_update
                )
                VALUES
                (
                    ?, ?
                )
                """,
                (
                    ticker,
                    today
                ))

                print(
                    f"{ticker:<6}"
                    f" "
                    f"Close="
                    f"{latest['Close']:.2f}"
                )

            except Exception as e:

                print(
                    f"Error "
                    f"{ticker}: "
                    f"{e}"
                )

        conn.commit()

    except Exception as e:

        print(
            f"Batch failed:"
        )

        print(e)

# ==========================================
# Summary
# ==========================================

cursor.execute("""
SELECT COUNT(*)
FROM prices
""")

price_count = cursor.fetchone()[0]

conn.close()

print("\n" + "=" * 70)
print("YFINANCE PRICE UPDATE COMPLETE")
print("=" * 70)

print(
    f"\nPrices Table Rows: "
    f"{price_count}"
)
