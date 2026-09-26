import sqlite3

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

ticker = input(
    "Enter ticker: "
).upper()

new_status = input(
    "Status (PENDING, REVIEWED, APPROVED, REJECTED): "
).upper()

cursor.execute("""
UPDATE research_queue
SET status = ?
WHERE ticker = ?
""",
(
    new_status,
    ticker
))

conn.commit()

print(
    f"{ticker} updated"
)

conn.close()
