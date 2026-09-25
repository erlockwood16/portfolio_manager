import subprocess
import sys

from pathlib import Path
from datetime import datetime

# ==========================================
# Project Root
# ==========================================

ROOT = Path(__file__).resolve().parent.parent

# ==========================================
# Weekly Pipeline
# ==========================================

PIPELINE = [

    # SEC Financials

    "fundamentals/sec_loader_multi_year.py",

    "fundamentals/extract_shares_outstanding.py",

    # Derived Metrics

    "fundamentals/calculate_sec_metrics.py",

    "fundamentals/calculate_market_metrics.py",

    # Analytics Refresh

    "analytics/refactor_factor_scores.py"

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
    f"weekly_"
    f"{datetime.today().strftime('%Y%m%d_%H%M%S')}.log"
)

# ==========================================
# Start
# ==========================================

print("\n" + "=" * 80)
print("INVESTMENT ADVISOR WEEKLY UPDATE")
print("=" * 80)

print(
    f"\nPython:\n{sys.executable}"
)

print(
    f"\nLog File:\n{log_file}"
)

# ==========================================
# Execute Pipeline
# ==========================================

with open(
    log_file,
    "w",
    encoding="utf-8"
) as log:

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
        # Verify File Exists
        # ----------------------------------

        if not script_path.exists():

            msg = (
                f"\nFILE NOT FOUND:\n"
                f"{script_path}"
            )

            print(msg)

            log.write(msg + "\n")

            break

        # ----------------------------------
        # Run Script
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

            # STDOUT

            if result.stdout:

                log.write(
                    "\nSTDOUT:\n"
                )

                log.write(
                    result.stdout
                )

            # STDERR

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
                f"\nEXCEPTION:\n{e}"
            )

            break

# ==========================================
# Complete
# ==========================================

print("\n" + "=" * 80)
print("WEEKLY UPDATE FINISHED")
print("=" * 80)

print(
    f"\nReview Log:\n{log_file}"
)
