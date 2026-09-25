import sqlite3

conn = sqlite3.connect("InvestmentAdvisor.db")
cursor = conn.cursor()

cursor.execute(
    """
    SELECT
        ticker,
        pe_ratio,
        revenue_growth,
        earnings_growth,
        debt_to_equity,
        roe
    FROM fundamentals
    ORDER BY ticker
    """
)

rows = cursor.fetchall()

print("\nFUNDAMENTALS\n")

for row in rows:
    ticker, pe_ratio, revenue_growth, earnings_growth, debt_to_equity, roe = row
    print(
        f"{ticker:<8}"
        f"PE={pe_ratio} "
        f"RevGrowth={revenue_growth}% "
        f"EPSGrowth={earnings_growth}% "
        f"D/E={debt_to_equity} "
        f"ROE={roe}%"
    )

conn.close()
