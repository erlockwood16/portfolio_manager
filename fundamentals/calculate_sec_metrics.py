import sqlite3
import pandas as pd

from datetime import datetime

# ==========================================
# Database
# ==========================================

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

# ==========================================
# Create Metrics Table
# ==========================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS fundamental_metrics (

    ticker TEXT PRIMARY KEY,

    revenue_growth REAL,

    earnings_growth REAL,

    asset_growth REAL,

    net_margin REAL,

    debt_ratio REAL,

    roa REAL,

    quality_score REAL,

    calculated_date TEXT

)
""")

conn.commit()

# ==========================================
# Load SEC Financials
# ==========================================

query = """
SELECT

    ticker,

    fiscal_year,

    revenue,

    net_income,

    assets,

    liabilities

FROM sec_financials

ORDER BY
    ticker,
    fiscal_year DESC
"""

df = pd.read_sql_query(
    query,
    conn
)

if df.empty:

    print(
        "\nNo SEC financials found."
    )

    conn.close()

    raise SystemExit

print(
    f"\nLoaded "
    f"{len(df):,} "
    f"financial records"
)

# ==========================================
# Calculate Metrics
# ==========================================

results = []

processed = 0

for ticker, group in df.groupby(
    "ticker"
):

    group = group.sort_values(
        "fiscal_year",
        ascending=False
    )

    if len(group) < 2:

        continue

    current = group.iloc[0]

    prior = group.iloc[1]

    revenue_growth = None
    earnings_growth = None
    asset_growth = None
    net_margin = None
    debt_ratio = None
    roa = None
    quality_score = None

    # --------------------------------------
    # Revenue Growth
    # --------------------------------------

    if (

        pd.notna(
            current["revenue"]
        )

        and

        pd.notna(
            prior["revenue"]
        )

        and

        prior["revenue"] != 0

    ):

        revenue_growth = round(

            (
                (
                    current["revenue"]
                    -
                    prior["revenue"]
                )

                /

                abs(
                    prior["revenue"]
                )
            )

            * 100,

            2

        )

    # --------------------------------------
    # Earnings Growth
    # --------------------------------------

    if (

        pd.notna(
            current["net_income"]
        )

        and

        pd.notna(
            prior["net_income"]
        )

        and

        prior["net_income"] != 0

    ):

        earnings_growth = round(

            (
                (
                    current["net_income"]
                    -
                    prior["net_income"]
                )

                /

                abs(
                    prior["net_income"]
                )
            )

            * 100,

            2

        )

    # --------------------------------------
    # Asset Growth
    # --------------------------------------

    if (

        pd.notna(
            current["assets"]
        )

        and

        pd.notna(
            prior["assets"]
        )

        and

        prior["assets"] != 0

    ):

        asset_growth = round(

            (
                (
                    current["assets"]
                    -
                    prior["assets"]
                )

                /

                abs(
                    prior["assets"]
                )
            )

            * 100,

            2

        )

    # --------------------------------------
    # Net Margin
    # --------------------------------------

    if (

        pd.notna(
            current["revenue"]
        )

        and

        pd.notna(
            current["net_income"]
        )

        and

        current["revenue"] != 0

    ):

        net_margin = round(

            (
                current["net_income"]

                /

                current["revenue"]

            )

            * 100,

            2

        )

    # --------------------------------------
    # Debt Ratio
    # --------------------------------------

    if (

        pd.notna(
            current["assets"]
        )

        and

        pd.notna(
            current["liabilities"]
        )

        and

        current["assets"] != 0

    ):

        debt_ratio = round(

            (
                current["liabilities"]

                /

                current["assets"]

            )

            * 100,

            2

        )

    # --------------------------------------
    # Return on Assets
    # --------------------------------------

    if (

        pd.notna(
            current["net_income"]
        )

        and

        pd.notna(
            current["assets"]
        )

        and

        current["assets"] != 0

    ):

        roa = round(

            (
                current["net_income"]

                /

                current["assets"]

            )

            * 100,

            2

        )

    # --------------------------------------
    # Quality Score
    # --------------------------------------

    components = []

    if revenue_growth is not None:

        components.append(
            max(
                0,
                min(
                    100,
                    revenue_growth
                )
            )
        )

    if earnings_growth is not None:

        components.append(
            max(
                0,
                min(
                    100,
                    earnings_growth
                )
            )
        )

    if net_margin is not None:

        components.append(
            max(
                0,
                min(
                    100,
                    net_margin
                )
            )
        )

    if roa is not None:

        components.append(
            max(
                0,
                min(
                    100,
                    roa
                )
            )
        )

    if components:

        quality_score = round(

            sum(components)

            /

            len(components),

            2

        )

    # --------------------------------------
    # Store Results
    # --------------------------------------

    results.append(

        (

            ticker,

            revenue_growth,

            earnings_growth,

            asset_growth,

            net_margin,

            debt_ratio,

            roa,

            quality_score,

            datetime.today().strftime(
                "%Y-%m-%d"
            )

        )

    )

    processed += 1

# ==========================================
# Save Results
# ==========================================

cursor.executemany("""
INSERT OR REPLACE
INTO fundamental_metrics
(

    ticker,

    revenue_growth,

    earnings_growth,

    asset_growth,

    net_margin,

    debt_ratio,

    roa,

    quality_score,

    calculated_date

)
VALUES
(
    ?, ?, ?, ?, ?, ?, ?, ?, ?
)
""",
results
)

conn.commit()

# ==========================================
# Verification
# ==========================================

cursor.execute("""
SELECT COUNT(*)
FROM fundamental_metrics
""")

count = cursor.fetchone()[0]

conn.close()

# ==========================================
# Summary
# ==========================================

print("\n" + "=" * 70)

print(
    "SEC METRICS CALCULATION COMPLETE"
)

print("=" * 70)

print(
    f"\nCompanies Processed : "
    f"{processed}"
)

print(
    f"Metrics Stored      : "
    f"{count}"
)

print("=" * 70)
