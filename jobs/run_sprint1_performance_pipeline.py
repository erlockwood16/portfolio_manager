import argparse
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT / "InvestmentAdvisor.db"
DEFAULT_BENCHMARK = "SPY"


def run_script(label, script_path, arguments=None, required=True):
    arguments = arguments or []
    if not script_path.exists():
        message = f"{label}: script not found: {script_path}"
        if required:
            raise FileNotFoundError(message)
        print(f"SKIPPED - {message}")
        return False

    command = [sys.executable, str(script_path), *arguments]
    print("\n" + "=" * 80)
    print(label)
    print("=" * 80)
    print("Command:", " ".join(command))

    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode != 0:
        if required:
            raise RuntimeError(
                f"{label} failed with exit code {result.returncode}."
            )
        print(f"SKIPPED - {label} returned exit code {result.returncode}.")
        return False
    return True


def table_row_count(connection, table_name):
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    if exists is None:
        return 0
    return connection.execute(
        f'SELECT COUNT(*) FROM "{table_name}"'
    ).fetchone()[0]


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Run the daily Sprint 1 performance pipeline and defer benchmark "
            "comparison until enough portfolio snapshots exist."
        )
    )
    parser.add_argument("--database", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--benchmark", default=DEFAULT_BENCHMARK)
    parser.add_argument(
        "--skip-snapshot",
        action="store_true",
        help="Do not run capture_daily_snapshot.py.",
    )
    parser.add_argument(
        "--minimum-comparison-rows",
        type=int,
        default=2,
        help="Minimum portfolio return rows required before benchmark comparison.",
    )
    args = parser.parse_args()

    database_path = args.database.resolve()
    benchmark = args.benchmark.strip().upper()
    if not database_path.exists():
        raise FileNotFoundError(f"Database not found: {database_path}")
    if not benchmark:
        raise ValueError("A benchmark ticker is required.")

    common_database_args = ["--database", str(database_path)]

    if not args.skip_snapshot:
        run_script(
            "Capture Daily Portfolio Snapshot",
            ROOT / "portfolio" / "capture_daily_snapshot.py",
            common_database_args,
            required=True,
        )

    run_script(
        "Update Benchmark Prices",
        ROOT / "ingestion" / "update_benchmark_prices.py",
        ["--tickers", benchmark, *common_database_args],
        required=True,
    )

    run_script(
        "Calculate Portfolio Returns",
        ROOT / "portfolio" / "calculate_portfolio_returns.py",
        [*common_database_args, "--full-refresh"],
        required=True,
    )

    with sqlite3.connect(database_path) as connection:
        portfolio_return_rows = table_row_count(connection, "portfolio_returns")
        snapshot_rows = table_row_count(connection, "portfolio_snapshots")

    comparison_ran = False
    if portfolio_return_rows >= args.minimum_comparison_rows:
        comparison_ran = run_script(
            "Calculate Benchmark Comparison",
            ROOT / "portfolio" / "calculate_benchmark_comparison.py",
            [
                *common_database_args,
                "--benchmark",
                benchmark,
                "--full-refresh",
            ],
            required=True,
        )
    else:
        print("\n" + "=" * 80)
        print("BENCHMARK COMPARISON DEFERRED")
        print("=" * 80)
        print(f"Portfolio snapshots:    {snapshot_rows:,}")
        print(f"Portfolio return rows:  {portfolio_return_rows:,}")
        print(
            "Required return rows:   "
            f"{args.minimum_comparison_rows:,}"
        )
        print(
            "Continue running this job daily. Benchmark comparison will start "
            "automatically after enough observations exist."
        )

    print("\n" + "=" * 80)
    print("SPRINT 1 DAILY PIPELINE COMPLETE")
    print("=" * 80)
    print(f"Run timestamp:          {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"Database:               {database_path}")
    print(f"Benchmark:              {benchmark}")
    print(f"Portfolio snapshots:    {snapshot_rows:,}")
    print(f"Portfolio return rows:  {portfolio_return_rows:,}")
    print(
        "Benchmark comparison:    "
        + ("COMPLETED" if comparison_ran else "DEFERRED")
    )
    print("=" * 80)


if __name__ == "__main__":
    main()
