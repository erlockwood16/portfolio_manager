import subprocess
import sys

from pathlib import Path
from datetime import datetime

# ==========================================
# Project Root
# ==========================================

ROOT = Path(__file__).resolve().parent.parent

# ==========================================
# Pipeline
# ==========================================

PIPELINE = [

    # --------------------------------------
    # Robinhood Import
    # --------------------------------------

    "portfolio/import_robinhood_transactions.py",

    # --------------------------------------
    # Portfolio Snapshot
    # --------------------------------------

    "portfolio/capture_daily_snapshot.py",

    # --------------------------------------
    # Market Data
    # --------------------------------------

    "ingestion/update_daily_prices.py",

    # --------------------------------------
    # Analytics
    # --------------------------------------

    "analytics/update_scores.py",

    "analytics/refactor_factor_scores.py",

    # --------------------------------------
    # Recommendations
    # --------------------------------------

    "analytics/find_buy_candidates.py",

    # --------------------------------------
    # Research
    # --------------------------------------

    "analytics/build_research_queue.py",

    # --------------------------------------
    # Portfolio
    # --------------------------------------

    "portfolio/recommend_allocations.py"

]

# ==========================================
# Logging
# ==========================================

log_dir = ROOT / "logs"

log_dir.mkdir(
    exist_ok=True
)

log_file = (
    log_dir
    /
    f"daily_"
    f"{datetime.today().strftime('%Y%m%d_%H%M%S')}.log"
)

# ==========================================
# Start
# ==========================================

print("\n" + "=" * 80)
print("INVESTMENT ADVISOR DAILY UPDATE")
print("=" * 80)

print(
    f"\nPython: "
    f"{sys.executable}"
)

print(
    f"\nLog File:\n{log_file}\n"
)

# ==========================================
# Execute Pipeline
# ==========================================

with open(log_file, "w", encoding="utf-8") as log:

    for script in PIPELINE:

        script_path = ROOT / script

        print(
            f"\nRunning:\n{script}"
        )

        log.write(
            "\n" + "=" * 80 + "\n"
        )

        log.write(
            f"RUNNING: {script}\n"
        )

        # ----------------------------------
        # File Exists Check
        # ----------------------------------

        if not script_path.exists():

            msg = (
                f"FILE NOT FOUND:\n"
                f"{script_path}"
            )

            print(msg)

            log.write(msg + "\n")

            break

        # ----------------------------------
        # Execute Script
        # ----------------------------------

        try:

            result = subprocess.run(

                [
                    sys.executable,
                    str(script_path)
                ],

                capture_output=True,

                text=True,

                cwd=ROOT

            )

            # stdout

            if result.stdout:

                log.write(
                    "\nSTDOUT:\n"
                )

                log.write(
                    result.stdout
                )

            # stderr

            if result.stderr:

                log.write(
                    "\nSTDERR:\n"
                )

                log.write(
                    result.stderr
                )

            # Success

            if result.returncode == 0:

                print(
                    "SUCCESS"
                )

            # Failure

            else:

                print(
                    "FAILED"
                )

                print(
                    "\nError:\n"
                )

                print(
                    result.stderr
                )

                break

        except Exception as e:

            print(
                "EXCEPTION"
            )

            print(e)

            log.write(
                "\nEXCEPTION:\n"
            )

            log.write(
                str(e)
            )

            break

# ==========================================
# Complete
# ==========================================

print("\n" + "=" * 80)
print("DAILY UPDATE FINISHED")
print("=" * 80)

print(
    f"\nReview log:\n{log_file}"
)
