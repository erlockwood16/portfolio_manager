import sqlite3
from datetime import datetime

# ==========================================
# Database
# ==========================================

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

ticker = input(
    "\nTicker: "
).upper()

# ==========================================
# Pull Analytics
# ==========================================

cursor.execute("""
SELECT
    overall_score
FROM analytics_scores
WHERE ticker = ?
""",
(ticker,)
)

analytics = cursor.fetchone()

if not analytics:

    print(
        f"No analytics found for {ticker}"
    )

    conn.close()
    exit()

overall_score = analytics[0]

print(
    f"\nCurrent Overall Score: "
    f"{overall_score}"
)

# ==========================================
# User Inputs
# ==========================================

bull_case = input(
    "\nBull Case: "
)

bear_case = input(
    "\nBear Case: "
)

key_risks = input(
    "\nKey Risks: "
)

catalysts = input(
    "\nCatalysts: "
)

fair_value = float(
    input(
        "\nFair Value Estimate: "
    )
)

target_position_pct = float(
    input(
        "\nTarget Position %: "
    )
)

status = input(
    "\nStatus "
    "(PENDING, APPROVED, REJECTED): "
).upper()

# ==========================================
# Save Thesis
# ==========================================

cursor.execute("""
INSERT OR REPLACE INTO investment_thesis
(
    ticker,

    bull_case,
    bear_case,

    key_risks,
    catalysts,

    fair_value,

    target_position_pct,

    status,

    last_updated
)
VALUES
(
    ?, ?, ?, ?, ?, ?, ?, ?, ?
)
""",
(
    ticker,

    bull_case,
    bear_case,

    key_risks,
    catalysts,

    fair_value,

    target_position_pct,

    status,

    datetime.today().strftime(
        "%Y-%m-%d"
    )
))

conn.commit()

print(
    f"\nInvestment thesis saved "
    f"for {ticker}"
)

conn.close()
