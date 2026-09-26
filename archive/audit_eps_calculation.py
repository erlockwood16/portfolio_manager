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

print("\n" + "=" * 100)
print("EPS / PE CALCULATION AUDIT")
print("=" * 100)

# ==========================================
# Companies
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

# ==========================================
# Process
# ==========================================

for ticker in tickers:

    print("\n" + "-" * 100)
    print(f"TICKER: {ticker}")
    print("-" * 100)

    # --------------------------------------
    # Price
    # --------------------------------------

    cursor.execute("""
    SELECT
        close_price,
        price_date
    FROM prices
    WHERE ticker = ?
    ORDER BY price_date DESC
    LIMIT 1
    """,
    (ticker,)
    )

    price_row = cursor.fetchone()

    if not price_row:

        print("No price data found")

        continue

    current_price = price_row[0]
    price_date = price_row[1]

    # --------------------------------------
    # SEC Financials
    # --------------------------------------

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
    LIMIT 1
    """,
    (ticker,)
    )

    financials = cursor.fetchone()

    if not financials:

        print("No SEC financial data found")

        continue

    fiscal_year = financials[0]
    revenue = financials[1]
    net_income = financials[2]
    assets = financials[3]
    liabilities = financials[4]
    shares = financials[5]

    # --------------------------------------
    # Equity
    # --------------------------------------

    equity = None

    if (
        assets is not None
        and liabilities is not None
    ):

        equity = assets - liabilities

    # --------------------------------------
    # EPS
    # --------------------------------------

    eps = None

    if (
        shares
        and shares > 0
        and net_income is not None
    ):

        eps = net_income / shares

    # --------------------------------------
    # PE
    # --------------------------------------

    pe = None

    if (
        eps
        and eps > 0
    ):

        pe = current_price / eps

    # --------------------------------------
    # BVPS
    # --------------------------------------

    bvps = None

    if (
        equity
        and shares
        and shares > 0
    ):

        bvps = equity / shares

    # --------------------------------------
    # P/B
    # --------------------------------------

    pb = None

    if (
        bvps
        and bvps > 0
    ):

        pb = current_price / bvps

    # --------------------------------------
    # Print Audit
    # --------------------------------------

    print(
        f"Price Date        : {price_date}"
    )

    print(
        f"Current Price     : {current_price:,.2f}"
    )

    print(
        f"Fiscal Year       : {fiscal_year}"
    )

    print()

    print(
        f"Revenue           : "
        f"{revenue:,.0f}"
        if revenue is not None
        else "Revenue           : None"
    )

    print(
        f"Net Income        : "
        f"{net_income:,.0f}"
        if net_income is not None
        else "Net Income        : None"
    )

    print(
        f"Assets            : "
        f"{assets:,.0f}"
        if assets is not None
        else "Assets            : None"
    )

    print(
        f"Liabilities       : "
        f"{liabilities:,.0f}"
        if liabilities is not None
        else "Liabilities       : None"
    )

    print(
        f"Equity            : "
        f"{equity:,.0f}"
        if equity is not None
        else "Equity            : None"
    )

    print()

    print(
        f"Shares Outstanding: "
        f"{shares:,.0f}"
        if shares is not None
        else "Shares Outstanding: None"
    )

    print(
        f"EPS               : "
        f"{eps:.4f}"
        if eps is not None
        else "EPS               : None"
    )

    print(
        f"PE Ratio          : "
        f"{pe:.2f}"
        if pe is not None
        else "PE Ratio          : None"
    )

    print()

    print(
        f"Book Value/Share  : "
        f"{bvps:.4f}"
        if bvps is not None
        else "Book Value/Share  : None"
    )

    print(
        f"Price-to-Book     : "
        f"{pb:.2f}"
        if pb is not None
        else "Price-to-Book     : None"
    )

conn.close()

print(
    "\nAudit Complete."
)
