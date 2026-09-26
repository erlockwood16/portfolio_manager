import sqlite3
import pandas as pd

# ==========================================
# Configuration
# ==========================================

TOP_N = 50

# ==========================================
# Database
# ==========================================

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

query = """
SELECT

    ticker,

    value_score,

    quality_score,

    growth_score,

    momentum_score,

    overall_score

FROM analytics_scores

WHERE overall_score IS NOT NULL

ORDER BY overall_score DESC

LIMIT ?
"""

df = pd.read_sql_query(
    query,
    conn,
    params=(TOP_N,)
)

conn.close()

# ==========================================
# Display
# ==========================================

print("\n" + "=" * 100)
print(
    f"TOP {TOP_N} RANKED STOCKS"
)
print("=" * 100)

if df.empty:

    print(
        "\nNo ranked stocks found."
    )

else:

    print(
        df.to_string(
            index=False,
            justify="left"
        )
    )

# ==========================================
# Summary Statistics
# ==========================================

if not df.empty:

    print("\n" + "=" * 100)

    print(
        f"Stocks Displayed: "
        f"{len(df)}"
    )

    print(
        f"Highest Score : "
        f"{df['overall_score'].max():.2f}"
    )

    print(
        f"Average Score : "
        f"{df['overall_score'].mean():.2f}"
    )

    print(
        f"Lowest Score  : "
        f"{df['overall_score'].min():.2f}"
    )

    print("=" * 100)
