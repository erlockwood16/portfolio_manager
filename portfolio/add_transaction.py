import sqlite3

conn = sqlite3.connect("InvestmentAdvisor.db")
cursor = conn.cursor()

trade_date = "2026-08-08"
ticker = "MSFT"
transaction_type = "BUY"
quantity = 10
price = 500.00

cursor.execute("""
INSERT INTO transactions
(
    trade_date,
    ticker,
    transaction_type,
    quantity,
    price
)
VALUES (?, ?, ?, ?, ?)
""",
(
    trade_date,
    ticker,
    transaction_type,
    quantity,
    price
))

conn.commit()

print("Transaction Added")

conn.close()
