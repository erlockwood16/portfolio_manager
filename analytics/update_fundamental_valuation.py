from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT / "InvestmentAdvisor.db"


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()}


def ensure_fundamentals_schema(conn: sqlite3.Connection) -> None:
    if not table_exists(conn, "fundamentals"):
        raise RuntimeError("Required table 'fundamentals' does not exist.")

    existing = columns(conn, "fundamentals")
    required = {
        "pe_ratio": "REAL",
        "price_to_book": "REAL",
        "eps": "REAL",
        "book_value_per_share": "REAL",
        "last_updated": "TEXT",
    }
    for name, data_type in required.items():
        if name not in existing:
            conn.execute(f'ALTER TABLE fundamentals ADD COLUMN "{name}" {data_type}')


def load_latest_prices(conn: sqlite3.Connection) -> pd.DataFrame:
    if not table_exists(conn, "prices"):
        raise RuntimeError("Required table 'prices' does not exist.")

    return pd.read_sql_query(
        """
        WITH ranked AS (
            SELECT
                UPPER(TRIM(ticker)) AS ticker,
                CAST(close_price AS REAL) AS current_price,
                price_date,
                ROW_NUMBER() OVER (
                    PARTITION BY UPPER(TRIM(ticker))
                    ORDER BY price_date DESC
                ) AS rn
            FROM prices
            WHERE ticker IS NOT NULL
              AND close_price IS NOT NULL
              AND CAST(close_price AS REAL) > 0
        )
        SELECT ticker, current_price, price_date
        FROM ranked
        WHERE rn = 1
        """,
        conn,
    )


def load_latest_financials(conn: sqlite3.Connection) -> pd.DataFrame:
    if not table_exists(conn, "sec_financials"):
        raise RuntimeError("Required table 'sec_financials' does not exist.")

    return pd.read_sql_query(
        """
        WITH ranked AS (
            SELECT
                UPPER(TRIM(ticker)) AS ticker,
                fiscal_year,
                CAST(net_income AS REAL) AS net_income,
                CAST(assets AS REAL) AS assets,
                CAST(liabilities AS REAL) AS liabilities,
                CAST(shares_outstanding AS REAL) AS shares_outstanding,
                ROW_NUMBER() OVER (
                    PARTITION BY UPPER(TRIM(ticker))
                    ORDER BY fiscal_year DESC
                ) AS rn
            FROM sec_financials
            WHERE ticker IS NOT NULL
        )
        SELECT ticker, fiscal_year, net_income, assets, liabilities, shares_outstanding
        FROM ranked
        WHERE rn = 1
        """,
        conn,
    )


def calculate_ratios(prices: pd.DataFrame, financials: pd.DataFrame) -> pd.DataFrame:
    data = prices.merge(financials, on="ticker", how="inner")
    if data.empty:
        raise RuntimeError("No tickers matched between prices and sec_financials.")

    numeric = ["current_price", "net_income", "assets", "liabilities", "shares_outstanding"]
    for column in numeric:
        data[column] = pd.to_numeric(data[column], errors="coerce")

    valid_shares = data["shares_outstanding"].where(data["shares_outstanding"] > 0)
    data["eps"] = data["net_income"] / valid_shares
    data["book_value_per_share"] = (data["assets"] - data["liabilities"]) / valid_shares

    # Negative or zero earnings/book value do not produce meaningful conventional multiples.
    data["pe_ratio"] = data["current_price"] / data["eps"].where(data["eps"] > 0)
    data["price_to_book"] = data["current_price"] / data["book_value_per_share"].where(
        data["book_value_per_share"] > 0
    )

    for column in ["eps", "book_value_per_share", "pe_ratio", "price_to_book"]:
        data[column] = data[column].replace([np.inf, -np.inf], np.nan)

    # Reject implausible multiples rather than allowing bad source data to dominate percentiles.
    data["pe_ratio"] = data["pe_ratio"].where(data["pe_ratio"].between(0.1, 500.0))
    data["price_to_book"] = data["price_to_book"].where(
        data["price_to_book"].between(0.05, 100.0)
    )

    return data


def update_fundamentals(conn: sqlite3.Connection, ratios: pd.DataFrame) -> tuple[int, int, int]:
    updated_at = datetime.now().strftime("%Y-%m-%d")
    payload = []
    for row in ratios.itertuples(index=False):
        payload.append(
            (
                row.ticker,
                None if pd.isna(row.eps) else round(float(row.eps), 6),
                None if pd.isna(row.book_value_per_share) else round(float(row.book_value_per_share), 6),
                None if pd.isna(row.pe_ratio) else round(float(row.pe_ratio), 4),
                None if pd.isna(row.price_to_book) else round(float(row.price_to_book), 4),
                updated_at,
            )
        )

    conn.executemany(
        """
        INSERT INTO fundamentals (
            ticker, eps, book_value_per_share, pe_ratio, price_to_book, last_updated
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker) DO UPDATE SET
            eps = excluded.eps,
            book_value_per_share = excluded.book_value_per_share,
            pe_ratio = excluded.pe_ratio,
            price_to_book = excluded.price_to_book,
            last_updated = excluded.last_updated
        """,
        payload,
    )

    pe_count = int(ratios["pe_ratio"].notna().sum())
    pb_count = int(ratios["price_to_book"].notna().sum())
    return len(payload), pe_count, pb_count


def run_update(db_path: str | Path) -> int:
    database = Path(db_path).resolve()
    if not database.exists():
        raise FileNotFoundError(f"Database not found: {database}")

    with sqlite3.connect(database) as conn:
        ensure_fundamentals_schema(conn)
        prices = load_latest_prices(conn)
        financials = load_latest_financials(conn)
        ratios = calculate_ratios(prices, financials)
        updated, pe_count, pb_count = update_fundamentals(conn, ratios)
        conn.commit()

    print("\n" + "=" * 76)
    print("FUNDAMENTAL VALUATION UPDATE COMPLETE")
    print("=" * 76)
    print(f"Database:              {database}")
    print(f"Tickers matched:       {updated:,}")
    print(f"Valid P/E ratios:      {pe_count:,}")
    print(f"Valid price/book:      {pb_count:,}")
    print("Negative/zero earnings or book value were stored with NULL multiples.")
    print("=" * 76)
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calculate fundamentals.pe_ratio and fundamentals.price_to_book from prices and SEC financials."
    )
    parser.add_argument("--database", type=Path, default=DEFAULT_DB_PATH)
    args = parser.parse_args()
    run_update(args.database)


if __name__ == "__main__":
    main()
