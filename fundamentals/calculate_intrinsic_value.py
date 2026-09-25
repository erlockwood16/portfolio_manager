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
# Create Table
# ==========================================

cursor.execute("""
DROP TABLE IF EXISTS intrinsic_values
""")

cursor.execute("""
CREATE TABLE intrinsic_values (

    ticker TEXT PRIMARY KEY,

    current_price REAL,

    hybrid_score REAL,

    estimated_upside_pct REAL,

    estimated_fair_value REAL,

    calculated_date TEXT

)
""")

conn.commit()

# ==========================================
# Load Data
# ==========================================

query = """
WITH latest_prices AS (

    SELECT

        p1.ticker,

        p1.close_price

    FROM prices p1

    INNER JOIN (

        SELECT

            ticker,

            MAX(price_date) AS max_date

        FROM prices

        GROUP BY ticker

    ) p2

    ON p1.ticker = p2.ticker

    AND p1.price_date = p2.max_date

)

SELECT

    a.ticker,

    a.value_score,

    a.quality_score,

    a.growth_score,

    a.momentum_score,

    a.overall_score,

    fm.revenue_growth,

    fm.net_margin,

    fm.roa,

    fm.debt_ratio,

    lp.close_price

FROM analytics_scores a

JOIN fundamental_metrics fm
ON a.ticker = fm.ticker

JOIN latest_prices lp
ON a.ticker = lp.ticker
"""

df = pd.read_sql_query(
    query,
    conn
)



if df.empty:

    print(
        "No data available."
    )

    conn.close()

    raise SystemExit

# ==========================================
# Hybrid Valuation Model
# ==========================================

records = []

for _, row in df.iterrows():

    hybrid_score = (

          row["overall_score"] * 0.50

        + max(
            0,
            min(
                100,
                row["revenue_growth"]
                if pd.notna(
                    row["revenue_growth"]
                )
                else 0
            )
        ) * 0.15

        + max(
            0,
            min(
                100,
                row["net_margin"]
                if pd.notna(
                    row["net_margin"]
                )
                else 0
            )
        ) * 0.15

        + max(
            0,
            min(
                100,
                row["roa"]
                if pd.notna(
                    row["roa"]
                )
                else 0
            )
        ) * 0.10

        + max(
            0,
            min(
                100,
                100 - row["debt_ratio"]
                if pd.notna(
                    row["debt_ratio"]
                )
                else 0
            )
        ) * 0.10

    )

    hybrid_score = round(
        hybrid_score,
        2
    )

    upside_pct = round(

        (
            hybrid_score
            - 50
        )
        * 0.8,

        2

    )

    fair_value = round(

        row["close_price"]

        *

        (
            1
            +
            upside_pct
            / 100
        ),

        2

    )

    records.append(

        (

            row["ticker"],

            row["close_price"],

            hybrid_score,

            upside_pct,

            fair_value,

            datetime.today().strftime(
                "%Y-%m-%d"
            )

        )

    )

# ==========================================
# Save
# ==========================================

cursor.executemany("""
INSERT OR REPLACE INTO intrinsic_values
(

    ticker,

    current_price,

    hybrid_score,

    estimated_upside_pct,

    estimated_fair_value,

    calculated_date

)
VALUES
(
    ?, ?, ?, ?, ?, ?
)
""",
records
)

df = df.drop_duplicates(
    subset=["ticker"]
)

conn.commit()

cursor.execute("""
SELECT COUNT(*)
FROM intrinsic_values
""")

count = cursor.fetchone()[0]

conn.close()

print("\n" + "=" * 70)

print(
    "HYBRID VALUATION COMPLETE"
)

print("=" * 70)

print(
    f"\nCompanies Valued: "
    f"{count}"
)

print("=" * 70)
