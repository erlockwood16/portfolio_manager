import sqlite3

conn = sqlite3.connect("InvestmentAdvisor.db")
cursor = conn.cursor()

cursor.execute("""
SELECT
    p.ticker,
    p.shares,
    p.cost_basis,
    pr.close_price
FROM positions p
JOIN prices pr
ON p.ticker = pr.ticker
""")

rows = cursor.fetchall()

total_portfolio = 0

print("\nPORTFOLIO SUMMARY\n")

for ticker, shares, cost_basis, market_price in rows:

    market_value = shares * market_price

    cost_value = shares * cost_basis

    gain_loss = market_value - cost_value

    total_portfolio += market_value

    print(
        f"{ticker} | "
        f"Shares: {shares} | "
        f"Market Value: ${market_value:,.2f} | "
        f"Gain/Loss: ${gain_loss:,.2f}"
    )

print("\n--------------------")
print(f"Portfolio Value: ${total_portfolio:,.2f}")

conn.close()
