import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT / "InvestmentAdvisor.db"
DEFAULT_BENCHMARK = "SPY"


def table_exists(connection, table_name):
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone() is not None


def get_columns(connection, table_name):
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table_name})")}


def validate_sources(connection):
    requirements = {
        "portfolio_returns": {"return_date", "portfolio_value"},
        "benchmark_prices": {"ticker", "price_date", "close_price"},
    }
    for table_name, required in requirements.items():
        if not table_exists(connection, table_name):
            raise RuntimeError(f"Required table '{table_name}' does not exist.")
        missing = required - get_columns(connection, table_name)
        if missing:
            raise RuntimeError(
                f"{table_name} is missing required columns: {', '.join(sorted(missing))}"
            )


def ensure_output_table(connection):
    required = {
        "comparison_date", "benchmark_ticker", "benchmark_price_date",
        "portfolio_value", "benchmark_close", "portfolio_daily_return",
        "benchmark_daily_return", "daily_excess_return",
        "portfolio_cumulative_return", "benchmark_cumulative_return",
        "cumulative_alpha", "updated_timestamp",
    }
    if table_exists(connection, "benchmark_comparison"):
        existing = get_columns(connection, "benchmark_comparison")
        if not required.issubset(existing):
            backup = "benchmark_comparison_legacy_" + datetime.now().strftime("%Y%m%d_%H%M%S")
            connection.execute(f'ALTER TABLE benchmark_comparison RENAME TO "{backup}"')
            print(f"Backed up incompatible benchmark_comparison table as {backup}.")

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS benchmark_comparison (
            comparison_date TEXT NOT NULL,
            benchmark_ticker TEXT NOT NULL,
            benchmark_price_date TEXT NOT NULL,
            portfolio_value REAL NOT NULL,
            benchmark_close REAL NOT NULL,
            portfolio_daily_return REAL,
            benchmark_daily_return REAL,
            daily_excess_return REAL,
            portfolio_cumulative_return REAL NOT NULL,
            benchmark_cumulative_return REAL NOT NULL,
            cumulative_alpha REAL NOT NULL,
            updated_timestamp TEXT NOT NULL,
            PRIMARY KEY (comparison_date, benchmark_ticker)
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_benchmark_comparison_ticker_date
        ON benchmark_comparison (benchmark_ticker, comparison_date DESC)
        """
    )


def source_diagnostics(connection, benchmark):
    portfolio = connection.execute(
        "SELECT COUNT(*), MIN(return_date), MAX(return_date) FROM portfolio_returns"
    ).fetchone()
    benchmark_data = connection.execute(
        """SELECT COUNT(*), MIN(price_date), MAX(price_date)
           FROM benchmark_prices WHERE UPPER(TRIM(ticker)) = ?""",
        (benchmark,),
    ).fetchone()
    print("\nSOURCE DIAGNOSTICS")
    print("=" * 72)
    print(f"Portfolio rows: {portfolio[0]:,} | {portfolio[1] or 'N/A'} to {portfolio[2] or 'N/A'}")
    print(f"{benchmark} rows:       {benchmark_data[0]:,} | {benchmark_data[1] or 'N/A'} to {benchmark_data[2] or 'N/A'}")
    print("=" * 72)
    return portfolio, benchmark_data


def load_history(connection, benchmark, start_date=None, end_date=None):
    portfolio_query = """
        SELECT date(return_date) AS comparison_date, portfolio_value
        FROM portfolio_returns
        WHERE portfolio_value IS NOT NULL
    """
    params = []
    if start_date:
        portfolio_query += " AND date(return_date) >= date(?)"
        params.append(start_date)
    if end_date:
        portfolio_query += " AND date(return_date) <= date(?)"
        params.append(end_date)
    portfolio_query += " ORDER BY date(return_date)"

    price_columns = get_columns(connection, "benchmark_prices")
    price_expr = (
        "COALESCE(adjusted_close, close_price)"
        if "adjusted_close" in price_columns else "close_price"
    )
    benchmark_query = f"""
        SELECT date(price_date) AS benchmark_price_date,
               {price_expr} AS benchmark_close
        FROM benchmark_prices
        WHERE UPPER(TRIM(ticker)) = ?
          AND {price_expr} IS NOT NULL
        ORDER BY date(price_date)
    """

    portfolio = pd.read_sql_query(portfolio_query, connection, params=params)
    prices = pd.read_sql_query(benchmark_query, connection, params=(benchmark,))
    if portfolio.empty or prices.empty:
        return pd.DataFrame()

    portfolio["comparison_date"] = pd.to_datetime(portfolio["comparison_date"], errors="coerce")
    portfolio["portfolio_value"] = pd.to_numeric(portfolio["portfolio_value"], errors="coerce")
    prices["benchmark_price_date"] = pd.to_datetime(prices["benchmark_price_date"], errors="coerce")
    prices["benchmark_close"] = pd.to_numeric(prices["benchmark_close"], errors="coerce")
    portfolio = portfolio.dropna().sort_values("comparison_date")
    prices = prices.dropna().sort_values("benchmark_price_date")

    # Match each snapshot to the latest benchmark close on or before that date.
    # This supports snapshots captured on weekends, holidays, or after market close.
    merged = pd.merge_asof(
        portfolio,
        prices,
        left_on="comparison_date",
        right_on="benchmark_price_date",
        direction="backward",
    )
    merged = merged.dropna(subset=["benchmark_close"])
    merged = merged.drop_duplicates(subset=["comparison_date"], keep="last")
    return merged.reset_index(drop=True)


def calculate_comparison(data):
    results = data.copy()
    results["portfolio_daily_return"] = results["portfolio_value"].pct_change()
    results["benchmark_daily_return"] = results["benchmark_close"].pct_change()
    results["daily_excess_return"] = (
        results["portfolio_daily_return"] - results["benchmark_daily_return"]
    )
    results["portfolio_cumulative_return"] = (
        results["portfolio_value"] / results["portfolio_value"].iloc[0] - 1.0
    )
    results["benchmark_cumulative_return"] = (
        results["benchmark_close"] / results["benchmark_close"].iloc[0] - 1.0
    )
    results["cumulative_alpha"] = (
        results["portfolio_cumulative_return"]
        - results["benchmark_cumulative_return"]
    )
    results.loc[0, ["portfolio_daily_return", "benchmark_daily_return", "daily_excess_return"]] = None
    results["comparison_date"] = results["comparison_date"].dt.strftime("%Y-%m-%d")
    results["benchmark_price_date"] = results["benchmark_price_date"].dt.strftime("%Y-%m-%d")
    return results


def upsert_results(connection, benchmark, results, timestamp, full_refresh):
    if full_refresh:
        connection.execute(
            "DELETE FROM benchmark_comparison WHERE benchmark_ticker = ?", (benchmark,)
        )
    rows = []
    for row in results.itertuples(index=False):
        rows.append((
            row.comparison_date, benchmark, row.benchmark_price_date,
            float(row.portfolio_value), float(row.benchmark_close),
            None if pd.isna(row.portfolio_daily_return) else float(row.portfolio_daily_return),
            None if pd.isna(row.benchmark_daily_return) else float(row.benchmark_daily_return),
            None if pd.isna(row.daily_excess_return) else float(row.daily_excess_return),
            float(row.portfolio_cumulative_return),
            float(row.benchmark_cumulative_return), float(row.cumulative_alpha), timestamp,
        ))
    connection.executemany(
        """
        INSERT INTO benchmark_comparison (
            comparison_date, benchmark_ticker, benchmark_price_date,
            portfolio_value, benchmark_close, portfolio_daily_return,
            benchmark_daily_return, daily_excess_return,
            portfolio_cumulative_return, benchmark_cumulative_return,
            cumulative_alpha, updated_timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(comparison_date, benchmark_ticker) DO UPDATE SET
            benchmark_price_date=excluded.benchmark_price_date,
            portfolio_value=excluded.portfolio_value,
            benchmark_close=excluded.benchmark_close,
            portfolio_daily_return=excluded.portfolio_daily_return,
            benchmark_daily_return=excluded.benchmark_daily_return,
            daily_excess_return=excluded.daily_excess_return,
            portfolio_cumulative_return=excluded.portfolio_cumulative_return,
            benchmark_cumulative_return=excluded.benchmark_cumulative_return,
            cumulative_alpha=excluded.cumulative_alpha,
            updated_timestamp=excluded.updated_timestamp
        """, rows
    )
    return len(rows)


def print_summary(results, benchmark, database_path):
    latest = results.iloc[-1]
    print("\n" + "=" * 72)
    print("BENCHMARK COMPARISON COMPLETE")
    print("=" * 72)
    print(f"Database:             {database_path}")
    print(f"Benchmark:            {benchmark}")
    print(f"Matched observations: {len(results):,}")
    print(f"Comparison period:    {results.iloc[0]['comparison_date']} to {latest['comparison_date']}")
    print(f"Portfolio return:     {latest['portfolio_cumulative_return'] * 100:,.4f}%")
    print(f"{benchmark} return:           {latest['benchmark_cumulative_return'] * 100:,.4f}%")
    print(f"Cumulative alpha:     {latest['cumulative_alpha'] * 100:,.4f}%")
    print("=" * 72)
    print("Benchmark dates are matched as-of the latest trading date on or before each snapshot.")
    print("Portfolio returns remain unadjusted for deposits and withdrawals.")


def main():
    parser = argparse.ArgumentParser(description="Compare portfolio returns with a benchmark.")
    parser.add_argument("--database", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--benchmark", default=DEFAULT_BENCHMARK)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--full-refresh", action="store_true")
    args = parser.parse_args()

    benchmark = args.benchmark.strip().upper()
    database_path = args.database.resolve()
    if not database_path.exists():
        raise FileNotFoundError(f"Database not found: {database_path}")

    with sqlite3.connect(database_path) as connection:
        validate_sources(connection)
        ensure_output_table(connection)
        portfolio_stats, benchmark_stats = source_diagnostics(connection, benchmark)
        if portfolio_stats[0] == 0:
            raise RuntimeError("portfolio_returns is empty. Run calculate_portfolio_returns.py first.")
        if benchmark_stats[0] == 0:
            raise RuntimeError(
                f"benchmark_prices has no rows for {benchmark}. Run the benchmark loader "
                f"against this same database: {database_path}"
            )

        data = load_history(connection, benchmark, args.start_date, args.end_date)
        if data.empty:
            raise RuntimeError(
                "No benchmark price exists on or before any portfolio return date. "
                "Check the displayed source date ranges and confirm both scripts use the same database."
            )
        if len(data) < 2:
            raise RuntimeError("At least two matched portfolio dates are required.")

        results = calculate_comparison(data)
        count = upsert_results(
            connection, benchmark, results,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"), args.full_refresh,
        )
        connection.commit()

    if count != len(results):
        raise RuntimeError("Not all comparison rows were written.")
    print_summary(results, benchmark, database_path)


if __name__ == "__main__":
    main()
