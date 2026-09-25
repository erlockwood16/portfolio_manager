import sqlite3

conn = sqlite3.connect("InvestmentAdvisor.db")
cursor = conn.cursor()

# Stocks
cursor.execute("""
CREATE TABLE IF NOT EXISTS stocks (
    ticker TEXT PRIMARY KEY,
    company_name TEXT,
    sector TEXT,
    industry TEXT
)
""")

# Daily prices
cursor.execute("""
CREATE TABLE IF NOT EXISTS prices (
    ticker TEXT,
    price_date TEXT,
    open_price REAL,
    high_price REAL,
    low_price REAL,
    close_price REAL,
    volume INTEGER,
    PRIMARY KEY (ticker, price_date)
)
""")


# Buy/Sell transactions
cursor.execute("""
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT,
    ticker TEXT,
    transaction_type TEXT,
    quantity REAL,
    price REAL
)
""")

# Current holdings
cursor.execute("""
CREATE TABLE IF NOT EXISTS positions (
    ticker TEXT PRIMARY KEY,
    shares REAL,
    cost_basis REAL
)
""")

# Watchlist
cursor.execute("""
CREATE TABLE IF NOT EXISTS watchlist (
    ticker TEXT PRIMARY KEY
)
""")


# Transactions
cursor.execute("""
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT,
    ticker TEXT,
    transaction_type TEXT,
    quantity REAL,
    price REAL
)
""")

# Positions
cursor.execute("""
CREATE TABLE IF NOT EXISTS positions (
    ticker TEXT PRIMARY KEY,
    shares REAL,
    cost_basis REAL
)
""")

# Screen Scores

cursor.execute("""
CREATE TABLE IF NOT EXISTS screen_scores (
    ticker TEXT PRIMARY KEY,
    momentum_score REAL,
    overall_score REAL,
    last_updated TEXT
)
""")

# Analytics Scores
cursor.execute("""
CREATE TABLE IF NOT EXISTS analytics_scores (
    ticker TEXT PRIMARY KEY,
    sma20 REAL,
    sma50 REAL,
    sma200 REAL,
    momentum_score REAL,
    volatility REAL,
    overall_score REAL,
    score_date TEXT
)
""")



conn.commit()

print("All tables created successfully")

conn.close()
