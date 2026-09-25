import argparse
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

try:
    import yfinance as yf
except ImportError:
    yf = None

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT / "InvestmentAdvisor.db"
DEFAULT_TICKERS = ["SPY", "QQQ", "VOO"]
DEFAULT_START_DATE = "2010-01-01"


def normalize_tickers(values):
    return sorted({str(value).strip().upper() for value in values if str(value).strip()})


def ensure_tables(connection):
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS benchmark_prices (
            ticker TEXT NOT NULL,
            price_date TEXT NOT NULL,
            open_price REAL,
            high_price REAL,
            low_price REAL,
            close_price REAL NOT NULL,
            adjusted_close REAL,
            volume INTEGER,
            source TEXT NOT NULL,
            updated_timestamp TEXT NOT NULL,
            PRIMARY KEY (ticker, price_date)
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_benchmark_prices_date
        ON benchmark_prices (price_date)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_benchmark_prices_ticker_date
        ON benchmark_prices (ticker, price_date DESC)
        """
    )


def most_recent_date(connection, ticker):
    row = connection.execute(
        "SELECT MAX(price_date) FROM benchmark_prices WHERE ticker = ?",
        (ticker,),
    ).fetchone()
    return row[0] if row and row[0] else None


def determine_start_date(connection, ticker, requested_start, full_refresh):
    if full_refresh:
        return requested_start
    latest = most_recent_date(connection, ticker)
    if latest is None:
        return requested_start
    # Re-download a small overlap so corrected vendor prices are upserted.
    overlap_start = datetime.strptime(latest, "%Y-%m-%d") - timedelta(days=7)
    return max(overlap_start.strftime("%Y-%m-%d"), requested_start)


def download_ticker(ticker, start_date, end_date, retries=3):
    if yf is None:
        raise RuntimeError(
            "yfinance is not installed. Install it in the project environment with: "
            "python -m pip install yfinance"
        )

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            data = yf.download(
                ticker,
                start=start_date,
                end=end_date,
                auto_adjust=False,
                progress=False,
                actions=False,
                threads=False,
            )
            if data is None or data.empty:
                return pd.DataFrame()

            # yfinance can return MultiIndex columns even for one ticker.
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = [column[0] for column in data.columns]

            data = data.reset_index()
            date_column = "Date" if "Date" in data.columns else data.columns[0]
            data = data.rename(
                columns={
                    date_column: "price_date",
                    "Open": "open_price",
                    "High": "high_price",
                    "Low": "low_price",
                    "Close": "close_price",
                    "Adj Close": "adjusted_close",
                    "Volume": "volume",
                }
            )

            required = {"price_date", "close_price"}
            if not required.issubset(data.columns):
                raise ValueError(
                    f"Unexpected download columns for {ticker}: {list(data.columns)}"
                )

            for column in [
                "open_price",
                "high_price",
                "low_price",
                "close_price",
                "adjusted_close",
                "volume",
            ]:
                if column not in data.columns:
                    data[column] = None

            data["price_date"] = pd.to_datetime(
                data["price_date"], errors="coerce", utc=True
            ).dt.strftime("%Y-%m-%d")

            numeric_columns = [
                "open_price",
                "high_price",
                "low_price",
                "close_price",
                "adjusted_close",
                "volume",
            ]
            for column in numeric_columns:
                data[column] = pd.to_numeric(data[column], errors="coerce")

            data = data.dropna(subset=["price_date", "close_price"])
            data = data.drop_duplicates(subset=["price_date"], keep="last")
            return data
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(2 ** (attempt - 1))

    raise RuntimeError(f"Download failed for {ticker}: {last_error}")


def upsert_prices(connection, ticker, data, timestamp):
    rows = []
    for row in data.itertuples(index=False):
        volume = None if pd.isna(row.volume) else int(row.volume)
        rows.append(
            (
                ticker,
                row.price_date,
                None if pd.isna(row.open_price) else float(row.open_price),
                None if pd.isna(row.high_price) else float(row.high_price),
                None if pd.isna(row.low_price) else float(row.low_price),
                float(row.close_price),
                None if pd.isna(row.adjusted_close) else float(row.adjusted_close),
                volume,
                "YFINANCE",
                timestamp,
            )
        )

    connection.executemany(
        """
        INSERT INTO benchmark_prices (
            ticker, price_date, open_price, high_price, low_price,
            close_price, adjusted_close, volume, source, updated_timestamp
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker, price_date) DO UPDATE SET
            open_price = excluded.open_price,
            high_price = excluded.high_price,
            low_price = excluded.low_price,
            close_price = excluded.close_price,
            adjusted_close = excluded.adjusted_close,
            volume = excluded.volume,
            source = excluded.source,
            updated_timestamp = excluded.updated_timestamp
        """,
        rows,
    )
    return len(rows)


def sync_to_prices_table(connection, tickers):
    """Optionally make benchmarks available to existing analytics using prices."""
    table = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='prices'"
    ).fetchone()
    if table is None:
        return 0

    columns = {
        row[1] for row in connection.execute("PRAGMA table_info(prices)").fetchall()
    }
    required = {"ticker", "price_date", "close_price"}
    if not required.issubset(columns):
        return 0

    placeholders = ",".join("?" for _ in tickers)
    rows = connection.execute(
        f"""
        SELECT ticker, price_date, close_price
        FROM benchmark_prices
        WHERE ticker IN ({placeholders})
        """,
        tuple(tickers),
    ).fetchall()

    # Requires the unique ticker/date index already added to prices.
    connection.executemany(
        """
        INSERT INTO prices (ticker, price_date, close_price)
        VALUES (?, ?, ?)
        ON CONFLICT(ticker, price_date) DO UPDATE SET
            close_price = excluded.close_price
        """,
        rows,
    )
    return len(rows)


def print_summary(connection, results):
    print("\n" + "=" * 76)
    print("BENCHMARK PRICE UPDATE COMPLETE")
    print("=" * 76)
    print(f"{'Ticker':<10}{'Status':<12}{'Rows':>10}{'Latest Date':>18}")
    print("-" * 76)
    for result in results:
        latest = most_recent_date(connection, result["ticker"]) or "N/A"
        print(
            f"{result['ticker']:<10}{result['status']:<12}"
            f"{result['rows']:>10,}{latest:>18}"
        )
    print("=" * 76)


def main():
    parser = argparse.ArgumentParser(
        description="Download and upsert benchmark prices for portfolio comparison."
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=DEFAULT_TICKERS,
        help="Benchmark tickers (default: SPY QQQ VOO)",
    )
    parser.add_argument("--database", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--start-date", default=DEFAULT_START_DATE)
    parser.add_argument(
        "--end-date",
        default=(datetime.today() + timedelta(days=1)).strftime("%Y-%m-%d"),
        help="Exclusive end date; defaults to tomorrow to include today's close",
    )
    parser.add_argument(
        "--full-refresh",
        action="store_true",
        help="Reload the entire requested date range instead of incrementally updating",
    )
    parser.add_argument(
        "--sync-prices",
        action="store_true",
        help="Also upsert ticker/date/close into the existing prices table",
    )
    args = parser.parse_args()

    tickers = normalize_tickers(args.tickers)
    if not tickers:
        raise ValueError("At least one benchmark ticker is required.")

    database_path = args.database.resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    results = []

    with sqlite3.connect(database_path) as connection:
        ensure_tables(connection)

        for ticker in tickers:
            start_date = determine_start_date(
                connection, ticker, args.start_date, args.full_refresh
            )
            print(f"Downloading {ticker}: {start_date} through {args.end_date}...")
            try:
                data = download_ticker(ticker, start_date, args.end_date)
                if data.empty:
                    results.append({"ticker": ticker, "status": "NO DATA", "rows": 0})
                    print(f"No data returned for {ticker}.")
                    continue
                row_count = upsert_prices(connection, ticker, data, timestamp)
                connection.commit()
                results.append({"ticker": ticker, "status": "SUCCESS", "rows": row_count})
            except Exception as exc:
                connection.rollback()
                results.append({"ticker": ticker, "status": "FAILED", "rows": 0})
                print(f"ERROR {ticker}: {exc}", file=sys.stderr)

        if args.sync_prices:
            try:
                synced = sync_to_prices_table(connection, tickers)
                connection.commit()
                print(f"Synced {synced:,} benchmark rows to prices.")
            except sqlite3.OperationalError as exc:
                connection.rollback()
                print(
                    "Benchmark table updated, but prices sync failed. Ensure prices has "
                    "a UNIQUE index on (ticker, price_date). Error: " + str(exc),
                    file=sys.stderr,
                )

        print_summary(connection, results)

    if any(result["status"] == "FAILED" for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
