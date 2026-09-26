import sqlite3
import pandas as pd

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

WHERE overall_score >= 80

ORDER BY overall_score DESC
"""

df = pd.read_sql_query(
    query,
    conn
)

conn.close()

print(
    "\nSTRONG BUY CANDIDATES\n"
)

if df.empty:

    print(
        "No strong buys found."
    )

else:

    print(
        df.to_string(
            index=False
        )
    )

    print(
        f"\nCount: "
        f"{len(df)}"
    )
