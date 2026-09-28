import sqlite3
from pathlib import Path

DB_PATH = Path("database/portfolio.db")


def create_tables(conn):
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS benchmark_prices (
        symbol TEXT NOT NULL,
        price_date DATE NOT NULL,
        close_price REAL NOT NULL,
        daily_return REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (symbol, price_date)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS portfolio_returns (
        return_date DATE PRIMARY KEY,
        portfolio_value REAL NOT NULL,
        daily_return REAL,
        cumulative_return REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS benchmark_comparison (
        comparison_date DATE PRIMARY KEY,
        portfolio_return REAL,
        benchmark_return REAL,
        alpha REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS portfolio_attribution (
        snapshot_date DATE NOT NULL,
        ticker TEXT NOT NULL,
        market_value REAL NOT NULL,
        weight_pct REAL,
        pnl_dollar REAL,
        contribution_pct REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (snapshot_date, ticker)
    )
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_benchmark_prices_date
    ON benchmark_prices(price_date)
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_portfolio_returns_date
    ON portfolio_returns(return_date)
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_benchmark_comparison_date
    ON benchmark_comparison(comparison_date)
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_portfolio_attribution_date
    ON portfolio_attribution(snapshot_date)
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_portfolio_attribution_ticker
    ON portfolio_attribution(ticker)
    """)

    conn.commit()


def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)

    try:
        create_tables(conn)

        print("\n✅ Sprint 1 tables created successfully")
        print(f"Database: {DB_PATH}\n")

        cursor = conn.cursor()

        cursor.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type='table'
        ORDER BY name
        """)

        print("Tables:")
        for row in cursor.fetchall():
            print(f"  - {row[0]}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
