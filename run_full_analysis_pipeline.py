import argparse
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# =============================================================================
# CONFIGURATION
# =============================================================================

ROOT = Path(__file__).resolve().parent
DEFAULT_DB_PATH = ROOT / "InvestmentAdvisor.db"

NEW_TICKERS = [
    # Add custom investments here.
    "BX",
    "RDDT",
    "ARM",
    "CRWD",
]

BENCHMARK_TICKERS = ["SPY", "QQQ", "VOO"]
AUTO_IMPORT_PORTFOLIO = True
CONTINUE_ON_ERROR = False

# Each pipeline script is resolved relative to this file.
PIPELINE = [
    ("Update Daily Prices", "ingestion/update_daily_prices.py", []),
    (
        "Update Benchmark Prices",
        "ingestion/update_benchmark_prices.py",
        ["--tickers", *BENCHMARK_TICKERS],
    ),
    ("Update SEC Company Mappings", "fundamentals/update_sec_company_map.py", []),
    ("Update SEC Fundamentals", "fundamentals/update_sp500_fundamentals.py", []),
    ("Calculate SEC Metrics", "fundamentals/calculate_sec_metrics.py", []),
    ("Calculate Momentum Metrics", "analytics/calculate_momentum_metrics.py", []),
    ("Rebuild Factor Scores", "analytics/refactor_factor_scores.py", []),
    ("Calculate Intrinsic Values", "fundamentals/calculate_intrinsic_value.py", []),
    ("Generate Allocation Recommendations", "portfolio/recommend_allocations.py", []),
    ("Capture Portfolio Snapshot", "portfolio/capture_daily_snapshot.py", []),
]


def normalize_ticker(value):
    return str(value or "").strip().upper().replace(".", "-")


def table_exists(cursor, table_name):
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def column_exists(cursor, table_name, column_name):
    if not table_exists(cursor, table_name):
        return False
    columns = cursor.execute(f'PRAGMA table_info("{table_name}")').fetchall()
    return any(row[1].lower() == column_name.lower() for row in columns)


def add_tickers(cursor, tickers):
    added = 0
    invalid = []

    for raw_ticker in tickers:
        ticker = normalize_ticker(raw_ticker)
        if not ticker:
            invalid.append(raw_ticker)
            continue

        cursor.execute(
            "INSERT OR IGNORE INTO watchlist (ticker) VALUES (?)",
            (ticker,),
        )
        added += cursor.rowcount

    return added, invalid


def prepare_watchlist(db_path):
    manual_added = 0
    portfolio_added = 0
    benchmark_added = 0
    invalid_tickers = []
    portfolio_rows_read = 0
    portfolio_unique_tickers = 0
    notes = []

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS watchlist (
                ticker TEXT PRIMARY KEY
            )
            """
        )

        manual_added, invalid_manual = add_tickers(cursor, NEW_TICKERS)
        invalid_tickers.extend(invalid_manual)

        # Benchmarks are added to the watchlist so the general price loader can
        # also see them. A separate benchmark step still runs afterward.
        benchmark_added, invalid_benchmarks = add_tickers(cursor, BENCHMARK_TICKERS)
        invalid_tickers.extend(invalid_benchmarks)

        if AUTO_IMPORT_PORTFOLIO:
            if not table_exists(cursor, "portfolio_positions"):
                notes.append("Portfolio import skipped: portfolio_positions does not exist.")
            elif not column_exists(cursor, "portfolio_positions", "ticker"):
                notes.append("Portfolio import skipped: portfolio_positions has no ticker column.")
            else:
                shares_filter = ""
                if column_exists(cursor, "portfolio_positions", "shares"):
                    shares_filter = "WHERE COALESCE(shares, 0) > 0"

                source_rows = cursor.execute(
                    f"""
                    SELECT ticker
                    FROM portfolio_positions
                    {shares_filter}
                    """
                ).fetchall()
                portfolio_rows_read = len(source_rows)

                # Deduplicate before inserting. This prevents multiple broker,
                # lot, or source rows for the same security from inflating the
                # imported portfolio ticker count.
                portfolio_tickers = sorted(
                    {
                        normalize_ticker(row[0])
                        for row in source_rows
                        if normalize_ticker(row[0])
                    }
                )
                portfolio_unique_tickers = len(portfolio_tickers)
                portfolio_added, invalid_portfolio = add_tickers(
                    cursor,
                    portfolio_tickers,
                )
                invalid_tickers.extend(invalid_portfolio)

        conn.commit()

        watchlist_size = cursor.execute(
            "SELECT COUNT(DISTINCT ticker) FROM watchlist"
        ).fetchone()[0]

        watchlist_tickers = [
            row[0]
            for row in cursor.execute(
                "SELECT DISTINCT ticker FROM watchlist ORDER BY ticker"
            ).fetchall()
        ]

    return {
        "manual_added": manual_added,
        "portfolio_added": portfolio_added,
        "benchmark_added": benchmark_added,
        "portfolio_rows_read": portfolio_rows_read,
        "portfolio_unique_tickers": portfolio_unique_tickers,
        "watchlist_size": watchlist_size,
        "watchlist_tickers": watchlist_tickers,
        "invalid_tickers": invalid_tickers,
        "notes": notes,
    }


def run_pipeline_step(step_number, total_steps, step_name, relative_script, extra_args, db_path):
    script_path = ROOT / relative_script
    started = time.perf_counter()

    result_record = {
        "step": step_number,
        "name": step_name,
        "script": str(script_path),
        "status": "PENDING",
        "seconds": 0.0,
        "return_code": None,
        "stdout": "",
        "stderr": "",
    }

    print("\n" + "-" * 80)
    print(f"STEP {step_number:02d}/{total_steps:02d}: {step_name}")
    print(f"Script: {script_path}")

    if not script_path.exists():
        result_record["status"] = "MISSING"
        result_record["stderr"] = f"Script not found: {script_path}"
        print(result_record["stderr"])
        return result_record

    command = [sys.executable, str(script_path), *extra_args]

    # Pass the database path to child scripts through an environment variable.
    # Existing scripts that do not use the variable continue to work unchanged.
    import os

    child_environment = os.environ.copy()
    child_environment["INVESTMENT_ADVISOR_DB"] = str(db_path)

    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            capture_output=True,
            env=child_environment,
            check=False,
        )

        result_record["seconds"] = round(time.perf_counter() - started, 2)
        result_record["return_code"] = completed.returncode
        result_record["stdout"] = completed.stdout or ""
        result_record["stderr"] = completed.stderr or ""

        if completed.stdout.strip():
            print(completed.stdout.rstrip())
        if completed.stderr.strip():
            print("\nSTDERR:")
            print(completed.stderr.rstrip())

        if completed.returncode == 0:
            result_record["status"] = "SUCCESS"
        else:
            result_record["status"] = "FAILED"

    except Exception as exc:
        result_record["seconds"] = round(time.perf_counter() - started, 2)
        result_record["status"] = "ERROR"
        result_record["stderr"] = f"{type(exc).__name__}: {exc}"
        print(result_record["stderr"])

    print(
        f"Result: {result_record['status']} "
        f"({result_record['seconds']:.2f}s)"
    )
    return result_record


def print_watchlist_summary(summary):
    print("\n" + "=" * 80)
    print("WATCHLIST PREPARATION COMPLETE")
    print("=" * 80)
    print(f"Manual tickers added       : {summary['manual_added']:,}")
    print(f"Benchmark tickers added    : {summary['benchmark_added']:,}")
    print(f"Portfolio source rows read : {summary['portfolio_rows_read']:,}")
    print(f"Unique portfolio tickers   : {summary['portfolio_unique_tickers']:,}")
    print(f"Portfolio tickers added    : {summary['portfolio_added']:,}")
    print(f"Watchlist size             : {summary['watchlist_size']:,}")
    print("=" * 80)

    if summary["notes"]:
        for note in summary["notes"]:
            print(f"NOTE: {note}")

    if summary["invalid_tickers"]:
        print(
            "WARNING: Blank or invalid ticker values skipped: "
            + ", ".join(map(str, summary["invalid_tickers"]))
        )


def print_execution_summary(results, watchlist_summary, pipeline_seconds):
    successful = sum(row["status"] == "SUCCESS" for row in results)
    failed = sum(row["status"] in {"FAILED", "ERROR", "MISSING"} for row in results)
    skipped = sum(row["status"] == "SKIPPED" for row in results)

    print("\n" + "=" * 80)
    print("FULL ANALYSIS PIPELINE EXECUTION SUMMARY")
    print("=" * 80)
    print(f"Run completed              : {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"Watchlist size             : {watchlist_summary['watchlist_size']:,}")
    print(f"Unique portfolio tickers   : {watchlist_summary['portfolio_unique_tickers']:,}")
    print(f"Pipeline steps configured  : {len(PIPELINE):,}")
    print(f"Successful steps           : {successful:,}")
    print(f"Failed/missing steps       : {failed:,}")
    print(f"Skipped steps              : {skipped:,}")
    print(f"Pipeline runtime           : {pipeline_seconds:.2f}s")
    print("-" * 80)

    for row in results:
        print(
            f"{row['step']:>2}. "
            f"{row['name']:<39}"
            f"{row['status']:<10}"
            f"{row['seconds']:>8.2f}s"
        )

    if failed:
        print("-" * 80)
        print("FAILED STEP DETAILS")
        for row in results:
            if row["status"] in {"FAILED", "ERROR", "MISSING"}:
                detail = row["stderr"].strip() or "No error details returned."
                print(f"\n{row['name']} [{row['status']}]")
                print(detail)

    print("=" * 80)
    if failed:
        print("Pipeline completed with errors. Review the failed step details above.")
    else:
        print("Analysis complete. Refresh Streamlit to view updated rankings.")


def main():
    parser = argparse.ArgumentParser(
        description="Run the complete Investment Advisor update pipeline."
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Path to InvestmentAdvisor.db",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        default=CONTINUE_ON_ERROR,
        help="Continue running later steps after a failure.",
    )
    args = parser.parse_args()

    db_path = args.database.expanduser().resolve()
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    watchlist_summary = prepare_watchlist(db_path)
    print_watchlist_summary(watchlist_summary)

    print("\n" + "=" * 80)
    print("STARTING FULL ANALYSIS PIPELINE")
    print("=" * 80)
    print(f"Database: {db_path}")
    print(f"Python  : {sys.executable}")

    pipeline_started = time.perf_counter()
    results = []
    stop_remaining_steps = False

    for step_number, (step_name, script, extra_args) in enumerate(PIPELINE, start=1):
        if stop_remaining_steps:
            results.append(
                {
                    "step": step_number,
                    "name": step_name,
                    "script": str(ROOT / script),
                    "status": "SKIPPED",
                    "seconds": 0.0,
                    "return_code": None,
                    "stdout": "",
                    "stderr": "Skipped because a prior step failed.",
                }
            )
            continue

        result = run_pipeline_step(
            step_number=step_number,
            total_steps=len(PIPELINE),
            step_name=step_name,
            relative_script=script,
            extra_args=extra_args,
            db_path=db_path,
        )
        results.append(result)

        if result["status"] != "SUCCESS" and not args.continue_on_error:
            stop_remaining_steps = True

    pipeline_seconds = round(time.perf_counter() - pipeline_started, 2)
    print_execution_summary(results, watchlist_summary, pipeline_seconds)

    if any(row["status"] in {"FAILED", "ERROR", "MISSING"} for row in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
