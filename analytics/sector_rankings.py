import sqlite3
import pandas as pd

# ==========================================
# Database
# ==========================================

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

query = """
SELECT

    cu.sector,

    COUNT(*) AS companies,

    AVG(a.value_score) AS avg_value,

    AVG(a.quality_score) AS avg_quality,

    AVG(a.growth_score) AS avg_growth,

    AVG(a.momentum_score) AS avg_momentum,

    AVG(a.overall_score) AS avg_overall

FROM company_universe cu

JOIN analytics_scores a
ON cu.ticker = a.ticker

GROUP BY
    cu.sector
"""

df = pd.read_sql_query(
    query,
    conn
)

conn.close()

df = df.sort_values(
    "avg_overall",
    ascending=False
)

print("\nSECTOR RANKINGS\n")

print(
    df.to_string(
        index=False
    )
)