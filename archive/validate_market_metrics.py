import sqlite3

# ==========================================
# Database
# ==========================================

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

# ==========================================
# Load Market Metrics
# ==========================================

cursor.execute("""
SELECT
    ticker,
    pe_ratio,
    eps,
    book_value_per_share,
    price_to_book,
    revenue_growth,
    earnings_growth,
    roe,
    debt_to_equity
FROM fundamentals
ORDER BY ticker
""")

rows = cursor.fetchall()

print("\n" + "=" * 80)
print("MARKET METRICS VALIDATION")
print("=" * 80)

issues_found = False

for row in rows:

    ticker = row[0]

    pe = row[1]
    eps = row[2]
    bvps = row[3]
    pb = row[4]
    revenue_growth = row[5]
    earnings_growth = row[6]
    roe = row[7]
    debt_to_equity = row[8]

    issues = []

    # --------------------------------------
    # PE Validation
    # --------------------------------------

    if pe is None:

        issues.append("PE Missing")

    elif pe < 5:

        issues.append(f"PE Too Low ({pe})")

    elif pe > 100:

        issues.append(f"PE Too High ({pe})")

    # --------------------------------------
    # EPS Validation
    # --------------------------------------

    if eps is None:

        issues.append("EPS Missing")

    elif eps <= 0:

        issues.append(f"Negative/Zero EPS ({eps})")

    # --------------------------------------
    # Price To Book Validation
    # --------------------------------------

    if pb is None:

        issues.append("P/B Missing")

    elif pb < 0.5:

        issues.append(f"P/B Too Low ({pb})")

    elif pb > 20:

        issues.append(f"P/B Too High ({pb})")

    # --------------------------------------
    # Book Value Validation
    # --------------------------------------

    if bvps is None:

        issues.append("BVPS Missing")

    elif bvps <= 0:

        issues.append(f"Negative BVPS ({bvps})")

    # --------------------------------------
    # Growth Checks
    # --------------------------------------

    if revenue_growth is not None:

        if revenue_growth > 100:

            issues.append(
                f"Revenue Growth Suspicious ({revenue_growth}%)"
            )

        elif revenue_growth < -50:

            issues.append(
                f"Revenue Growth Very Negative ({revenue_growth}%)"
            )

    if earnings_growth is not None:

        if earnings_growth > 200:

            issues.append(
                f"Earnings Growth Suspicious ({earnings_growth}%)"
            )

        elif earnings_growth < -80:

            issues.append(
                f"Earnings Growth Very Negative ({earnings_growth}%)"
            )

    # --------------------------------------
    # ROE Check
    # --------------------------------------

    if roe is not None:

        if roe > 100:

            issues.append(
                f"ROE Very High ({roe}%)"
            )

        elif roe < -100:

            issues.append(
                f"ROE Very Negative ({roe}%)"
            )

    # --------------------------------------
    # Debt Check
    # --------------------------------------

    if debt_to_equity is not None:

        if debt_to_equity > 10:

            issues.append(
                f"Debt/Equity Extremely High ({debt_to_equity})"
            )

    # --------------------------------------
    # Print Issues
    # --------------------------------------

    if issues:

        issues_found = True

        print("\n" + "-" * 60)
        print(f"{ticker}")
        print("-" * 60)

        for issue in issues:

            print(f"• {issue}")

# ==========================================
# Completion
# ==========================================

if not issues_found:

    print(
        "\nNo validation issues found."
    )

conn.close()

print(
    "\nValidation Complete."
)
