import sqlite3

conn = sqlite3.connect("InvestmentAdvisor.db")
cursor = conn.cursor()

# Clear current positions
cursor.execute("DELETE FROM positions")

cursor.execute("""
SELECT
    ticker,
    transaction_type,
    quantity,
    price
FROM transactions
ORDER BY trade_date
""")

transactions = cursor.fetchall()

positions = {}

for ticker, transaction_type, quantity, price in transactions:

    if ticker not in positions:

        positions[ticker] = {
            "shares": 0,
            "cost": 0
        }

    if transaction_type.upper() == "BUY":

        positions[ticker]["shares"] += quantity
        positions[ticker]["cost"] += quantity * price

    elif transaction_type.upper() == "SELL":

        positions[ticker]["shares"] -= quantity

for ticker, values in positions.items():

    shares = values["shares"]

    if shares <= 0:
        continue

    cost_basis = values["cost"] / shares

    cursor.execute("""
    INSERT INTO positions
    (
        ticker,
        shares,
        cost_basis
    )
    VALUES (?, ?, ?)
    """,
    (
        ticker,
        shares,
        cost_basis
    ))

conn.commit()

print("Positions Updated")

conn.close()
