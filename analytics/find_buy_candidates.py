import sqlite3

from datetime import datetime

# -----------------------------------------
# Database Connection
# -----------------------------------------

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

# -----------------------------------------
# Clear Existing Recommendations
# -----------------------------------------

cursor.execute("""
DELETE FROM buy_candidates
""")

# -----------------------------------------
# Load Analytics Scores
# -----------------------------------------

cursor.execute("""
SELECT
    ticker,
    current_price,
    momentum_score,
    volatility,
    overall_score
FROM analytics_scores
ORDER BY overall_score DESC
""")

rows = cursor.fetchall()

run_date = datetime.today().strftime(
    "%Y-%m-%d"
)

print("\n" + "=" * 70)
print("INVESTMENT OPPORTUNITIES")
print("=" * 70)

saved_count = 0

for row in rows:

    ticker = row[0]
    price = row[1]
    momentum = row[2]
    volatility = row[3]
    score = row[4]

    # -----------------------------------------
    # Recommendation Logic
    # -----------------------------------------

    if score >= 85 and momentum >= 90:

        recommendation = "STRONG BUY"

    elif score >= 70 and momentum >= 70:

        recommendation = "BUY"

    elif score >= 50:

        recommendation = "WATCH"

    else:

        recommendation = "AVOID"

    # -----------------------------------------
    # Save To Database
    # -----------------------------------------

    cursor.execute("""
    INSERT OR REPLACE INTO buy_candidates
    (
        ticker,
        current_price,
        momentum_score,
        volatility,
        overall_score,
        recommendation,
        run_date
    )
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
    (
        ticker,
        price,
        momentum,
        volatility,
        score,
        recommendation,
        run_date
    ))

    saved_count += 1

    print(
        f"{ticker:<8}"
        f"Price=${price:>8.2f}  "
        f"Momentum={momentum:>5.1f}  "
        f"Vol={volatility:>6.2f}  "
        f"Score={score:>6.2f}  "
        f"{recommendation}"
    )

conn.commit()

print(
    f"\nSaved {saved_count} recommendations"
)

conn.close()
