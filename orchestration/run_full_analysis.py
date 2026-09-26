import subprocess
import sys
import time

# ==========================================
# Pipeline Definition
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
        "Capture Portfolio Snapshot",
        "portfolio/capture_daily_snapshot.py"
    )

]

# ==========================================
# Execution
# ==========================================

results = []

pipeline_start = time.time()

print("\n" + "=" * 80)
print("INVESTMENT ADVISOR ANALYSIS PIPELINE")
print("=" * 80)

for step_name, script in PIPELINE:

    print("\n" + "-" * 80)

    print(
        f"Running: {step_name}"
    )

    print(
        f"Script: {script}"
    )

    start = time.time()

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
            start,

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

        print(
            f"ERROR: {e}"
        )

        break

# ==========================================
# Summary
# ==========================================

total_runtime = round(

    time.time()

    - pipeline_start,

    2

)

print("\n" + "=" * 80)
print("PIPELINE SUMMARY")
print("=" * 80)

for step, status, secs in results:

    print(

        f"{step:<35}"

        f"{status:<10}"

        f"{secs:>8}s"

    )

successes = len(
    [
        r
        for r in results
        if r[1] == "SUCCESS"
    ]
)

print("\n" + "-" * 80)

print(
    f"Steps Completed : "
    f"{successes}"
)

print(
    f"Total Runtime   : "
    f"{total_runtime}s"
)

print("=" * 80)
