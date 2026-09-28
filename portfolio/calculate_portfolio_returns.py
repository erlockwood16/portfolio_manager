import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT / "InvestmentAdvisor.db"


def ensure_output_table(connection):
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS portfolio_returns (
            return_date TEXT PRIMARY KEY,
            portfolio_value REAL NOT NULL,
            daily_return REAL,
            cumulative_return REAL NOT NULL,
            updated_timestamp TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_portfolio_returns_date
        ON portfolio_returns (return_date DESC)
        """
    )


def validate_snapshot_table(connection):
    table = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = 'portfolio_snapshots'
        """
    ).fetchone()
    if table is None:
        raise RuntimeError("Required table 'portfolio_snapshots' does not exist.")

    columns = {
        row[1]
        for row in connection.execute(
            "PRAGMA table_info(portfolio_snapshots)"
        ).fetchall()
    }
    required = {"snapshot_date", "total_account_value"}
    missing = required - columns
    if missing:
        raise RuntimeError(
            "portfolio_snapshots is missing required columns: "
            + ", ".join(sorted(missing))
        )


def load_snapshots(connection, start_date=None, end_date=None):
    conditions = ["total_account_value IS NOT NULL"]
    parameters = []

    if start_date:
        conditions.append("date(snapshot_date) >= date(?)")
        parameters.append(start_date)
    if end_date:
        conditions.append("date(snapshot_date) <= date(?)")
        parameters.append(end_date)

    query = f"""
        SELECT
            date(snapshot_date) AS return_date,
            total_account_value AS portfolio_value
        FROM portfolio_snapshots
        WHERE {' AND '.join(conditions)}
        ORDER BY date(snapshot_date), rowid
    """
    snapshots = pd.read_sql_query(query, connection, params=parameters)
    if snapshots.empty:
        return snapshots

    snapshots["return_date"] = pd.to_datetime(
        snapshots["return_date"], errors="coerce"
    )
    snapshots["portfolio_value"] = pd.to_numeric(
        snapshots["portfolio_value"], errors="coerce"
    )
    snapshots = snapshots.dropna(subset=["return_date", "portfolio_value"])
    snapshots = snapshots[snapshots["portfolio_value"] > 0]

    # If multiple snapshots exist for one date, retain the final stored snapshot.
    snapshots = snapshots.drop_duplicates(subset=["return_date"], keep="last")
    return snapshots.sort_values("return_date").reset_index(drop=True)


def calculate_returns(snapshots):
    if snapshots.empty:
        return snapshots

    results = snapshots.copy()
    results["daily_return"] = results["portfolio_value"].pct_change()
    first_value = results.loc[0, "portfolio_value"]
    results["cumulative_return"] = results["portfolio_value"] / first_value - 1.0
    results.loc[0, "daily_return"] = None
    results["return_date"] = results["return_date"].dt.strftime("%Y-%m-%d")
    return results


def replace_returns(connection, results, timestamp, full_refresh=False,
                    start_date=None, end_date=None):
    if full_refresh:
        connection.execute("DELETE FROM portfolio_returns")
    elif start_date or end_date:
        conditions = []
        parameters = []
        if start_date:
            conditions.append("date(return_date) >= date(?)")
            parameters.append(start_date)
        if end_date:
            conditions.append("date(return_date) <= date(?)")
            parameters.append(end_date)
        connection.execute(
            f"DELETE FROM portfolio_returns WHERE {' AND '.join(conditions)}",
            parameters,
        )

    rows = [
        (
            row.return_date,
            float(row.portfolio_value),
            None if pd.isna(row.daily_return) else float(row.daily_return),
            float(row.cumulative_return),
            timestamp,
        )
        for row in results.itertuples(index=False)
    ]
    connection.executemany(
        """
        INSERT INTO portfolio_returns (
            return_date, portfolio_value, daily_return,
            cumulative_return, updated_timestamp
        )
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(return_date) DO UPDATE SET
            portfolio_value = excluded.portfolio_value,
            daily_return = excluded.daily_return,
            cumulative_return = excluded.cumulative_return,
            updated_timestamp = excluded.updated_timestamp
        """,
        rows,
    )
    return len(rows)


def print_summary(results, database_path):
    print("\n" + "=" * 72)
    print("PORTFOLIO RETURNS CALCULATION COMPLETE")
    print("=" * 72)
    print(f"Database:          {database_path}")
    print(f"Rows calculated:   {len(results):,}")
    if not results.empty:
        latest = results.iloc[-1]
        daily = latest["daily_return"]
        daily_text = "N/A" if pd.isna(daily) else f"{daily * 100:,.4f}%"
        print(f"First date:        {results.iloc[0]['return_date']}")
        print(f"Latest date:       {latest['return_date']}")
        print(f"Latest value:      ${latest['portfolio_value']:,.2f}")
        print(f"Latest daily:      {daily_text}")
        print(f"Cumulative return: {latest['cumulative_return'] * 100:,.4f}%")
    print("=" * 72)
    print(
        "Note: returns are based on changes in total_account_value and are not "
        "adjusted for deposits or withdrawals."
    )


def main():
    parser = argparse.ArgumentParser(
        description="Calculate daily and cumulative returns from portfolio snapshots."
    )
    parser.add_argument("--database", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--start-date", help="Inclusive date in YYYY-MM-DD format")
    parser.add_argument("--end-date", help="Inclusive date in YYYY-MM-DD format")
    parser.add_argument(
        "--full-refresh",
        action="store_true",
        help="Delete and rebuild all rows in portfolio_returns",
    )
    args = parser.parse_args()

    database_path = args.database.resolve()
    if not database_path.exists():
        raise FileNotFoundError(f"Database not found: {database_path}")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(database_path) as connection:
        validate_snapshot_table(connection)
        ensure_output_table(connection)
        snapshots = load_snapshots(connection, args.start_date, args.end_date)
        if snapshots.empty:
            raise RuntimeError("No valid portfolio snapshots were found.")

        results = calculate_returns(snapshots)
        row_count = replace_returns(
            connection,
            results,
            timestamp,
            full_refresh=args.full_refresh,
            start_date=args.start_date,
            end_date=args.end_date,
        )
        connection.commit()

    if row_count != len(results):
        raise RuntimeError("Not all calculated return rows were written.")
    print_summary(results, database_path)


if __name__ == "__main__":
    main()
