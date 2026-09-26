import sqlite3
import subprocess
import sys
import time

# ==========================================
# CONFIGURATION
# ==========================================

NEW_TICKERS = [

    # Add custom investments here

    "BX",
    "RDDT",
    "ARM",
    "CRWD"

]

AUTO_IMPORT_PORTFOLIO = True

# ==========================================
# DATABASE
# ==========================================

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

# ==========================================
# Ensure Watchlist Exists
# ==========================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS watchlist (

    ticker TEXT PRIMARY KEY

)
""")

# ==========================================
# Add Manual Tickers
# ==========================================

added_watchlist = 0

for ticker in NEW_TICKERS:

    ticker = ticker.upper()

    cursor.execute("""
    INSERT OR IGNORE
    INTO watchlist
    (
        ticker
    )
    VALUES
    (
        ?
    )
    """,
    (ticker,)
    )

    added_watchlist += cursor.rowcount

# ==========================================
# Import Portfolio Holdings
# ==========================================

portfolio_added = 0

if AUTO_IMPORT_PORTFOLIO:

    try:

        cursor.execute("""
        SELECT DISTINCT ticker
        FROM portfolio_positions
        """)

        portfolio_tickers = [

            row[0]
            for row in cursor.fetchall()
        ]

        for ticker in portfolio_tickers:

            cursor.execute("""
            INSERT OR IGNORE
            INTO watchlist
            (
                ticker
            )
            VALUES
            (
                ?
            )
            """,
            (ticker,)
            )

            portfolio_added += cursor.rowcount

    except Exception as e:

        print(
            f"Portfolio import skipped: {e}"
        )

conn.commit()

cursor.execute("""
SELECT COUNT(*)
FROM watchlist
""")

watchlist_size = cursor.fetchone()[0]

conn.close()

# ==========================================
# Summary
# ==========================================

print("\n" + "=" * 80)

print(
    "UNIVERSE UPDATE COMPLETE"
)

print("=" * 80)

print(
    f"Manual Tickers Added   : "
    f"{added_watchlist}"
)

print(
    f"Portfolio Tickers Added: "
    f"{portfolio_added}"
)

print(
    f"Watchlist Size         : "
    f"{watchlist_size}"
)

print("=" * 80)

# ==========================================
# PIPELINE
# ==========================================

PIPELINE = [

    (
        "Update Daily Prices",
        "ingestion/update_daily_prices.py"
    ),

    (
        "Update SEC Company Map",
        "fundamentals/update_sec_company_map.py"
    ),

    (
        "Update SEC Fundamentals",
        "fundamentals/update_sp500_fundamentals.py"
    ),

    (
        "Calculate SEC Metrics",
        "fundamentals/calculate_sec_metrics.py"
    ),

    (
        "Calculate Momentum Metrics",
        "analytics/calculate_momentum_metrics.py"
    ),

    (
        "Rebuild Factor Scores",
        "analytics/refactor_factor_scores.py"
    ),

    (
        "Calculate Intrinsic Values",
        "fundamentals/calculate_intrinsic_value.py"
    ),

    (
        "Generate Allocations",
        "portfolio/recommend_allocations.py"
    ),

    (
        "Capture Snapshot",
        "portfolio/capture_daily_snapshot.py"
    )

]

# ==========================================
# EXECUTION
# ==========================================

results = []

pipeline_start = time.time()

print("\n" + "=" * 80)

print(
    "STARTING FULL ANALYSIS PIPELINE"
)

print("=" * 80)

for step_name, script in PIPELINE:

    print("\n" + "-" * 80)

    print(
        f"Running: {step_name}"
    )

    start_time = time.time()

    try:

        result = subprocess.run(

            [
                sys.executable,
                script
            ],

            text=True,

            capture_output=True

        )

        elapsed = round(

            time.time()
            -
            start_time,

            2

        )

        if result.returncode == 0:

            results.append(

                (
                    step_name,
                    "SUCCESS",
                    elapsed
                )

            )

            print(
                f"SUCCESS ({elapsed}s)"
            )

        else:

            results.append(

                (
                    step_name,
                    "FAILED",
                    elapsed
                )

            )

            print(
                f"FAILED ({elapsed}s)"
            )

            print(
                result.stderr
            )

            break

    except Exception as e:

        results.append(

            (
                step_name,
                "ERROR",
                0
            )

        )

        print(e)

        break

# ==========================================
# FINAL SUMMARY
# ==========================================

runtime = round(

    time.time()
    -
    pipeline_start,

    2

)

print("\n" + "=" * 80)

print(
    "PIPELINE SUMMARY"
)

print("=" * 80)

for step, status, secs in results:

    print(

        f"{step:<35}"

        f"{status:<10}"

        f"{secs:>8}s"

    )

success_count = len(

    [

        r

        for r in results

        if r[1] == "SUCCESS"

    ]

)

print("\n" + "-" * 80)

print(
    f"Completed Steps : "
    f"{success_count}"
)

print(
    f"Runtime         : "
    f"{runtime}s"
)

print("=" * 80)

print(
    "\nAnalysis complete. "
    "Refresh Streamlit "
    "to view updated rankings."
)
