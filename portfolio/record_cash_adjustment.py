import sqlite3

# ==========================================
# Configuration
# ==========================================

ADJUSTMENT_DATE = "2026-09-24"

ACTUAL_CASH = 5681.33

NOTES = (
    "Robinhood cash reconciliation adjustment"
)

# ==========================================
# Database
# ==========================================

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

# ==========================================
# Create Table
# ==========================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS cash_adjustments (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    adjustment_date TEXT NOT NULL,

    amount REAL NOT NULL,

    notes TEXT,

    created_at TEXT DEFAULT CURRENT_TIMESTAMP

)
""")

# ==========================================
# Get Imported Cash
# ==========================================

cursor.execute("""
SELECT cash_balance
FROM portfolio_cash
WHERE source = 'ROBINHOOD'
""")

result = cursor.fetchone()

if not result:

    print(
        "\nNo Robinhood cash balance found."
    )

    conn.close()

    quit()

imported_cash = result[0]

adjustment = round(
    ACTUAL_CASH - imported_cash,
    2
)

# ==========================================
# Save Adjustment
# ==========================================

cursor.execute("""
INSERT INTO cash_adjustments
(
    adjustment_date,
    amount,
    notes
)
VALUES
(
    ?, ?, ?
)
""",
(
    ADJUSTMENT_DATE,
    adjustment,
    NOTES
))

conn.commit()

# ==========================================
# Summary
# ==========================================

print("\n" + "=" * 60)
print("CASH RECONCILIATION RECORDED")
print("=" * 60)

print(
    f"\nImported Cash : "
    f"${imported_cash:,.2f}"
)

print(
    f"Actual Cash   : "
    f"${ACTUAL_CASH:,.2f}"
)

print(
    f"Adjustment    : "
    f"${adjustment:,.2f}"
)

print(
    f"\nNotes:\n{NOTES}"
)

conn.close()
