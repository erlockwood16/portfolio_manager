import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "InvestmentAdvisor.db"


def ensure_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cash_balances (
            broker TEXT NOT NULL,
            as_of_date TEXT NOT NULL,
            cash_balance REAL NOT NULL,
            source TEXT NOT NULL,
            created_timestamp TEXT NOT NULL,
            PRIMARY KEY (broker, as_of_date)
        )
    """)


def main():
    parser = argparse.ArgumentParser(
        description="Store the current broker cash balance for portfolio snapshots."
    )
    parser.add_argument("cash_balance", type=float, help="Current withdrawable/broker cash balance")
    parser.add_argument("--broker", default="ROBINHOOD")
    parser.add_argument("--as-of-date", default=datetime.today().strftime("%Y-%m-%d"))
    parser.add_argument("--database", type=Path, default=DEFAULT_DB)
    parser.add_argument("--source", default="MANUAL_BROKER_BALANCE")
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(args.database) as conn:
        ensure_table(conn)
        conn.execute("""
            INSERT INTO cash_balances
                (broker, as_of_date, cash_balance, source, created_timestamp)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(broker, as_of_date) DO UPDATE SET
                cash_balance = excluded.cash_balance,
                source = excluded.source,
                created_timestamp = excluded.created_timestamp
        """, (args.broker.upper(), args.as_of_date, round(args.cash_balance, 2), args.source, timestamp))
        conn.commit()

    print(f"Cash balance stored: {args.broker.upper()} ${args.cash_balance:,.2f} as of {args.as_of_date}")


if __name__ == "__main__":
    main()
