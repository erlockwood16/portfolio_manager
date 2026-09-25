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
# Rebuild Analytics Table
# ==========================================

cursor.execute("""
DROP TABLE IF EXISTS analytics_scores
""")

cursor.execute("""
CREATE TABLE analytics_scores (

    ticker TEXT PRIMARY KEY,

    value_score REAL,

    quality_score REAL,

    growth_score REAL,

    momentum_score REAL,

    overall_score REAL,

    calculated_date TEXT

)
""")

conn.commit()

# ==========================================
# Load Metrics
# ==========================================

query = """
SELECT

    fm.ticker,

    fm.revenue_growth,

    fm.earnings_growth,

    fm.net_margin,

    fm.asset_growth,

    fm.debt_ratio,

    fm.roa,

    mm.momentum_score

FROM fundamental_metrics fm

LEFT JOIN momentum_metrics mm
       ON fm.ticker = mm.ticker
"""

df = pd.read_sql_query(
    query,
    conn
)

if df.empty:

    print(
        "\nNo metrics available."
    )

    conn.close()

    raise SystemExit

# ==========================================
# Helper Functions
# ==========================================

def rank_to_score(series):

    """
    Convert a metric to a
    percentile score (0-100)
    """

    return (

        series.rank(
            pct=True
        )

        * 100

    ).round(2)


def inverse_rank_to_score(series):

    """
    Lower values are better
    """

    return (

        (
            1
            -
            series.rank(
                pct=True
            )
        )

        * 100

    ).round(2)

# ==========================================
# Value Score
# ==========================================

# Until PE/PB are added,
# use debt efficiency
# as a placeholder value factor

df["value_score"] = (

    inverse_rank_to_score(
        df["debt_ratio"]
    )

)

# ==========================================
# Quality Score
# ==========================================

quality_components = pd.DataFrame({

    "net_margin":

        rank_to_score(
            df["net_margin"]
        ),

    "roa":

        rank_to_score(
            df["roa"]
        )

})

df["quality_score"] = (

    quality_components.mean(
        axis=1
    )

).round(2)

# ==========================================
# Growth Score
# ==========================================

growth_components = pd.DataFrame({

    "revenue_growth":

        rank_to_score(
            df["revenue_growth"]
        ),

    "earnings_growth":

        rank_to_score(
            df["earnings_growth"]
        ),

    "asset_growth":

        rank_to_score(
            df["asset_growth"]
        )

})

df["growth_score"] = (

    growth_components.mean(
        axis=1
    )

).round(2)

# ==========================================
# Momentum Score
# ==========================================

df["momentum_score"] = (

    df["momentum_score"]

    .fillna(0)

    .round(2)

)

# ==========================================
# Overall Score
# ==========================================

df["overall_score"] = (

      df["value_score"]    * 0.25

    + df["quality_score"]  * 0.30

    + df["growth_score"]   * 0.25

    + df["momentum_score"] * 0.20

).round(2)

# ==========================================
# Save Scores
# ==========================================

scores = []

for _, row in df.iterrows():

    scores.append(

        (

            row["ticker"],

            float(row["value_score"]),

            float(row["quality_score"]),

            float(row["growth_score"]),

            float(row["momentum_score"]),

            float(row["overall_score"]),

            datetime.today().strftime(
                "%Y-%m-%d"
            )

        )

    )

cursor.executemany("""
INSERT OR REPLACE
INTO analytics_scores
(

    ticker,

    value_score,

    quality_score,

    growth_score,

    momentum_score,

    overall_score,

    calculated_date

)
VALUES
(
    ?, ?, ?, ?, ?, ?, ?
)
""",
scores
)

conn.commit()

# ==========================================
# Summary
# ==========================================

cursor.execute("""
SELECT COUNT(*)
FROM analytics_scores
""")

count = cursor.fetchone()[0]

conn.close()

print("\n" + "=" * 70)

print(
    "FACTOR SCORE REBUILD COMPLETE"
)

print("=" * 70)

print(
    f"\nCompanies Ranked: "
    f"{count}"
)

print(
    "\nWeights:"
)

print(
    "Value     = 25%"
)

print(
    "Quality   = 30%"
)

print(
    "Growth    = 25%"
)

print(
    "Momentum  = 20%"
)

print("=" * 70)
