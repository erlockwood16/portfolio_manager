import sqlite3
from datetime import datetime

# ----------------------------------
# Connect Database
# ----------------------------------

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

# ----------------------------------
# Load Qualified Candidates
# ----------------------------------

cursor.execute("""
SELECT
    ticker,
    overall_score,
    recommendation
FROM buy_candidates
WHERE recommendation IN
(
    'STRONG BUY',
    'BUY'
)
ORDER BY overall_score DESC
""")

candidates = cursor.fetchall()

added = 0

for candidate in candidates:

    ticker = candidate[0]
    score = candidate[1]
    recommendation = candidate[2]

    # ------------------------------
    # Prevent Duplicates
    # ------------------------------

    cursor.execute("""
    SELECT ticker
    FROM research_queue
    WHERE ticker = ?
    """,
    (ticker,)
    )

    if cursor.fetchone():

        print(
            f"{ticker} already exists"
        )

        continue

    cursor.execute("""
    INSERT INTO research_queue
    (
        ticker,
        overall_score,
        recommendation,
        added_date,
        status
    )
    VALUES (?, ?, ?, ?, ?)
    """,
    (
        ticker,
        score,
        recommendation,
        datetime.today().strftime(
            "%Y-%m-%d"
        ),
        "PENDING"
    ))

    added += 1

    print(
        f"Added {ticker}"
    )

conn.commit()

print(
    f"\n{added} stocks added to queue"
)

conn.close()
