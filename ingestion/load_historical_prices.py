import sqlite3
import yfinance as yf
import pandas as pd

# ==========================================
# Configuration
# ==========================================

START_DATE = "2020-01-01"

BATCH_SIZE = 100

# ==========================================
# Database
# ==========================================

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

# ==========================================
# Load Watchlist
# ==========================================

cursor.execute("""
SELECT ticker
FROM company_universe
ORDER BY ticker
""")

tickers = [
    row[0]
    for row in cursor.fetchall()
]

print(
    f"\nLoading history for "
    f"{len(tickers)} tickers"
)

# ==========================================
# Counters
# ==========================================

success_count = 0

skipped_count = 0

failure_count = 0

# ==========================================
# Process Batches
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
        f"\nBatch "
        f"{start + 1}"
        f" - "
        f"{min(start + BATCH_SIZE, len(tickers))}"
    )

    try:

        data = yf.download(

            tickers=batch,

            start=START_DATE,

            auto_adjust=False,

            progress=False,

            threads=True,

            group_by="ticker"

        )

        for ticker in batch:

            try:

                # ----------------------------------
                # Get Ticker Data
                # ----------------------------------

                try:

                    df = data[ticker]

                except KeyError:

                    print(
                        f"No data: {ticker}"
                    )

                    skipped_count += 1

                    continue

                if df.empty:

                    print(
                        f"Empty: {ticker}"
                    )

                    skipped_count += 1

                    continue

                rows_loaded = 0

                # ----------------------------------
                # Process Daily History
                # ----------------------------------

                for date, row in df.iterrows():

                    # Skip bad rows

                    if (

                        pd.isna(row["Open"])

                        or

                        pd.isna(row["High"])

                        or

                        pd.isna(row["Low"])

                        or

                        pd.isna(row["Close"])

                    ):

                        skipped_count += 1

                        continue

                    volume = (

                        0

                        if pd.isna(
                            row["Volume"]
                        )

                        else int(
                            row["Volume"]
                        )

                    )

                    cursor.execute("""
                    INSERT OR IGNORE
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

                        date.strftime(
                            "%Y-%m-%d"
                        ),

                        float(
                            row["Open"]
                        ),

                        float(
                            row["High"]
                        ),

                        float(
                            row["Low"]
                        ),

                        float(
                            row["Close"]
                        ),

                        volume
                    ))

                    rows_loaded += 1

                    success_count += 1

                print(
                    f"{ticker:<6}"
                    f" "
                    f"{rows_loaded:,}"
                    f" rows"
                )

            except Exception as e:

                failure_count += 1

                print(
                    f"{ticker}: {e}"
                )

        conn.commit()

    except Exception as e:

        print(
            "\nBatch Error:"
        )

        print(e)

# ==========================================
# Summary
# ==========================================

cursor.execute("""
SELECT COUNT(*)
FROM prices
""")

total_rows = cursor.fetchone()[0]

conn.close()

print("\n" + "=" * 70)
print("HISTORICAL LOAD COMPLETE")
print("=" * 70)

print(
    f"\nInserted Rows : "
    f"{success_count:,}"
)

print(
    f"Skipped Rows : "
    f"{skipped_count:,}"
)

print(
    f"Failed Tickers: "
    f"{failure_count:,}"
)

print(
    f"Total Price Rows: "
    f"{total_rows:,}"
)
