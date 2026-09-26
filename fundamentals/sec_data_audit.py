import sqlite3

# ==========================================
# Database
# ==========================================

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

# ==========================================
# Header
# ==========================================

print("\n" + "=" * 80)
print("SEC DATA AUDIT")
print("=" * 80)

# ==========================================
# Company Summary
# ==========================================

cursor.execute("""
SELECT DISTINCT ticker
FROM sec_financials
ORDER BY ticker
""")

tickers = [
    row[0]
    for row in cursor.fetchall()
]

for ticker in tickers:

    print("\n" + "-" * 80)
    print(f"TICKER: {ticker}")
    print("-" * 80)

    cursor.execute("""
    SELECT
        fiscal_year,
        revenue,
        net_income,
        assets,
        liabilities,
        shares_outstanding
    FROM sec_financials
    WHERE ticker = ?
    ORDER BY fiscal_year DESC
    """,
    (ticker,)
    )

    rows = cursor.fetchall()

    print(
        f"{'YEAR':<8}"
        f"{'REVENUE':<18}"
        f"{'NET INCOME':<18}"
        f"{'ASSETS':<18}"
        f"{'LIABILITIES':<18}"
        f"{'SHARES':<18}"
    )

    for row in rows:

        year = row[0]

        revenue = (
            "MISSING"
            if row[1] is None
            else f"{row,.0f}"
        )

        income = (
            "MISSING"
            if row[2] is None
            else f"{row,.0f}"
        )

        assets = (
            "MISSING"
            if row[3] is None
            else f"{row,.0f}"
        )

        liabilities = (
            "MISSING"
            if row[4] is None
            else f"{row,.0f}"
        )

        shares = (
            "MISSING"
            if row[5] is None
            else f"{row,.0f}"
        )

        print(
            f"{year:<8}"
            f"{revenue:<18}"
            f"{income:<18}"
            f"{assets:<18}"
            f"{liabilities:<18}"
            f"{shares:<18}"
        )

# ==========================================
# Missing Data Report
# ==========================================

print("\n" + "=" * 80)
print("MISSING DATA REPORT")
print("=" * 80)

cursor.execute("""
SELECT
    ticker,
    fiscal_year,
    revenue,
    net_income,
    assets,
    liabilities,
    shares_outstanding
FROM sec_financials
ORDER BY ticker,
         fiscal_year DESC
""")

rows = cursor.fetchall()

issues_found = False

for row in rows:

    missing_fields = []

    if row[2] is None:
        missing_fields.append("Revenue")

    if row[3] is None:
        missing_fields.append("Net Income")

    if row[4] is None:
        missing_fields.append("Assets")

    if row[5] is None:
        missing_fields.append("Liabilities")

    if row[6] is None:
        missing_fields.append("Shares")

    if missing_fields:

        issues_found = True

        print(
            f"{row[0]} "
            f"FY{row[1]} "
            f"Missing: "
            f"{', '.join(missing_fields)}"
        )

if not issues_found:

    print(
        "No missing SEC data detected."
    )

# ==========================================
# Year Alignment Audit
# ==========================================

print("\n" + "=" * 80)
print("YEAR ALIGNMENT AUDIT")
print("=" * 80)

for ticker in tickers:

    cursor.execute("""
    SELECT
        MIN(fiscal_year),
        MAX(fiscal_year),
        COUNT(*)
    FROM sec_financials
    WHERE ticker = ?
    """,
    (ticker,)
    )

    summary = cursor.fetchone()

    print(
        f"{ticker:<8}"
        f"Years={summary[2]} "
        f"Range={summary[0]}->{summary[1]}"
    )

# ==========================================
# Shares Audit
# ==========================================

print("\n" + "=" * 80)
print("SHARES OUTSTANDING AUDIT")
print("=" * 80)

cursor.execute("""
SELECT
    ticker,
    fiscal_year,
    shares_outstanding
FROM sec_financials
ORDER BY ticker,
         fiscal_year DESC
""")

rows = cursor.fetchall()

missing_shares = False

for row in rows:

    if row[2] is None:

        missing_shares = True

        print(
            f"{row[0]} FY{row[1]} Missing Shares"
        )

if not missing_shares:

    print(
        "All share records populated."
    )

conn.close()

print("\nAudit Complete.")
