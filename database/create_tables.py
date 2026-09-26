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

# Backfill Status Tracking

cursor.execute("""
CREATE TABLE IF NOT EXISTS backfill_status (
    ticker TEXT PRIMARY KEY,
    historical_loaded TEXT,
    load_date TEXT,
    rows_loaded INTEGER
)
""")

# Daily Update Status

cursor.execute("""
CREATE TABLE IF NOT EXISTS update_status (
    ticker TEXT PRIMARY KEY,
    last_update TEXT
)
""")

# Analytics Scores

cursor.execute("""
CREATE TABLE IF NOT EXISTS analytics_scores (
    ticker TEXT PRIMARY KEY,
    current_price REAL,
    sma20 REAL,
    sma50 REAL,
    sma200 REAL,
    momentum_score REAL,
    volatility REAL,
    overall_score REAL,
    score_date TEXT
)
""")

# Buy Candidates

cursor.execute("""
CREATE TABLE IF NOT EXISTS buy_candidates (
    ticker TEXT PRIMARY KEY,
    current_price REAL,
    momentum_score REAL,
    volatility REAL,
    overall_score REAL,
    recommendation TEXT,
    run_date TEXT
)
""")

# Research Queue
cursor.execute("""
CREATE TABLE IF NOT EXISTS research_queue (
    ticker TEXT PRIMARY KEY,
    overall_score REAL,
    recommendation TEXT,
    added_date TEXT,
    status TEXT
)
""")
# Fundamentals

cursor.execute("""
CREATE TABLE IF NOT EXISTS fundamentals (
    ticker TEXT PRIMARY KEY,
    market_cap REAL,
    pe_ratio REAL,
    revenue_growth REAL,
    debt_to_equity REAL,
    roe REAL,
    free_cash_flow REAL,
    last_updated TEXT
)
""")
# Research Memos

cursor.execute("""
CREATE TABLE IF NOT EXISTS research_memos (
    ticker TEXT PRIMARY KEY,
    memo_date TEXT,
    recommendation TEXT,
    overall_score REAL,
    memo_text TEXT
)
""")

# Fundamentals

cursor.execute("""
CREATE TABLE IF NOT EXISTS fundamentals (
    ticker TEXT PRIMARY KEY,

    market_cap REAL,

    pe_ratio REAL,

    revenue_growth REAL,

    earnings_growth REAL,

    debt_to_equity REAL,

    roe REAL,

    free_cash_flow REAL,

    last_updated TEXT
)
""")

# SEC Company Map
cursor.execute("""
CREATE TABLE IF NOT EXISTS sec_company_map (
    ticker TEXT PRIMARY KEY,
    cik TEXT
)
""")

# SEC Financials
cursor.execute("""
CREATE TABLE IF NOT EXISTS sec_financials (

    ticker TEXT,

    fiscal_year INTEGER,

    revenue REAL,

    net_income REAL,

    assets REAL,

    liabilities REAL,

    PRIMARY KEY (
        ticker,
        fiscal_year
    )

)
""")

# Investment Thesis
cursor.execute("""
CREATE TABLE IF NOT EXISTS investment_thesis (

    ticker TEXT PRIMARY KEY,

    bull_case TEXT,

    bear_case TEXT,

    key_risks TEXT,

    catalysts TEXT,

    fair_value REAL,

    target_position_pct REAL,

    status TEXT,

    last_updated TEXT

)
""")

# Recommended Allocations

cursor.execute("""
CREATE TABLE IF NOT EXISTS recommended_allocations (

    ticker TEXT PRIMARY KEY,

    overall_score REAL,

    allocation_pct REAL,

    position_value REAL,

    recommended_shares INTEGER,

    fair_value REAL,

    upside_pct REAL,

    generated_date TEXT

)
""")

# Indexes

cursor.execute("""
CREATE INDEX IF NOT EXISTS idx_prices_ticker_date
ON prices (
    ticker,
    price_date
)
""")

cursor.execute("""
CREATE INDEX IF NOT EXISTS idx_sec_financials_ticker_year
ON sec_financials (
    ticker,
    fiscal_year
)
""")

cursor.execute("""
CREATE INDEX IF NOT EXISTS idx_analytics_scores_ticker
ON analytics_scores (
    ticker
)
""")


conn.commit()

print("All tables created successfully")

conn.close()
