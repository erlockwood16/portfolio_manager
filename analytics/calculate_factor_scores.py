import sqlite3

from datetime import datetime

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

# ------------------------------------
# Load Fundamentals
# ------------------------------------

cursor.execute("""
SELECT
    ticker,
    pe_ratio,
    revenue_growth,
    earnings_growth,
    debt_to_equity,
    roe
FROM fundamentals
""")

rows = cursor.fetchall()

updated = 0

for row in rows:

    ticker = row[0]

    pe_ratio = row[1]
    revenue_growth = row[2]
    earnings_growth = row[3]
    debt_to_equity = row[4]
    roe = row[5]

    # ====================================
    # VALUE SCORE
    # ====================================

    if pe_ratio <= 15:

        value_score = 100

    elif pe_ratio <= 25:

        value_score = 80

    elif pe_ratio <= 35:

        value_score = 60

    elif pe_ratio <= 50:

        value_score = 40

    else:

        value_score = 20

    # ====================================
    # QUALITY SCORE
    # ====================================

    quality_score = 0

    if roe >= 20:

        quality_score += 50

    elif roe >= 10:

        quality_score += 25

    if debt_to_equity <= 0.5:

        quality_score += 50

    elif debt_to_equity <= 1.0:

        quality_score += 25

    # ====================================
    # GROWTH SCORE
    # ====================================

    avg_growth = (
        revenue_growth
        + earnings_growth
    ) / 2

    if avg_growth >= 30:

        growth_score = 100

    elif avg_growth >= 20:

        growth_score = 80

    elif avg_growth >= 10:

        growth_score = 60

    elif avg_growth >= 5:

        growth_score = 40

    else:

        growth_score = 20

    # ====================================
    # LOAD EXISTING ANALYTICS
    # ====================================

    cursor.execute("""
    SELECT
        momentum_score
    FROM analytics_scores
    WHERE ticker = ?
    """,
    (ticker,)
    )

    momentum_row = cursor.fetchone()

    if not momentum_row:

        print(
            f"No analytics found for {ticker}"
        )

        continue

    momentum_score = momentum_row[0]

    # ====================================
    # OVERALL SCORE
    # ====================================

    overall_score = round(

        (value_score * 0.30)

        + (quality_score * 0.30)

        + (growth_score * 0.20)

        + (momentum_score * 0.20),

        2

    )

    # ====================================
    # UPDATE ANALYTICS SCORES
    # ====================================

    cursor.execute("""
    UPDATE analytics_scores
    SET

        value_score = ?,

        quality_score = ?,

        growth_score = ?,

        overall_score = ?,

        score_date = ?

    WHERE ticker = ?
    """,
    (
        value_score,
        quality_score,
        growth_score,
        overall_score,
        datetime.today().strftime(
            "%Y-%m-%d"
        ),
        ticker
    ))

    updated += 1

    print(
        f"{ticker} | "
        f"Value={value_score} | "
        f"Quality={quality_score} | "
        f"Growth={growth_score} | "
        f"Overall={overall_score}"
    )

conn.commit()

print(
    f"\nUpdated {updated} stocks"
)

conn.close()
