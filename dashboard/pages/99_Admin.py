import streamlit as st
import subprocess
import sys

from pathlib import Path

# =====================================
# Config
# =====================================

ROOT = Path(__file__).resolve().parents[2]

# =====================================
# Helper
# =====================================

def run_script(script_path):

    result = subprocess.run(

        [
            sys.executable,
            str(script_path)
        ],

        capture_output=True,

        text=True,

        cwd=ROOT
    )

    return result

# =====================================
# Page
# =====================================

st.title(
    "⚙️ Administration"
)

st.write(
    "Run portfolio maintenance jobs."
)

# =====================================
# Daily Update
# =====================================

st.header(
    "Daily Update"
)

if st.button(
    "Run Daily Update"
):

    with st.spinner(
        "Running daily pipeline..."
    ):

        result = run_script(
            ROOT / "jobs" / "daily_update.py"
        )

    if result.returncode == 0:

        st.success(
            "Daily Update Complete"
        )

        st.text(
            result.stdout
        )

    else:

        st.error(
            "Daily Update Failed"
        )

        st.text(
            result.stderr
        )

# =====================================
# Weekly Update
# =====================================

st.header(
    "Weekly Update"
)

if st.button(
    "Run Weekly Update"
):

    with st.spinner(
        "Running weekly pipeline..."
    ):

        result = run_script(
            ROOT / "jobs" / "weekly_update.py"
        )

    if result.returncode == 0:

        st.success(
            "Weekly Update Complete"
        )

        st.text(
            result.stdout
        )

    else:

        st.error(
            "Weekly Update Failed"
        )

        st.text(
            result.stderr
        )
