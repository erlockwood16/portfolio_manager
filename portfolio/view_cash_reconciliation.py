import sqlite3

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

cursor.execute("""
SELECT cash_balance
FROM portfolio_cash
WHERE source='ROBINHOOD'
""")

cash = cursor.fetchone()[0]

cursor.execute("""
SELECT
    COALESCE(
        SUM(amount),
        0
    )
FROM cash_adjustments
""")

adjustments = cursor.fetchone()[0]

actual_cash = round(
    cash + adjustments,
    2
)

print("\nCASH RECONCILIATION\n")

print(
    f"Imported Cash : ${cash:,.2f}"
)

print(
    f"Adjustments   : ${adjustments:,.2f}"
)

print(
    f"Actual Cash   : ${actual_cash:,.2f}"
)

conn.close()
