import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT / "InvestmentAdvisor.db"


def table_exists(conn, name):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def columns(conn, name):
    return {row[1] for row in conn.execute(f'PRAGMA table_info("{name}")')}


def ensure_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_sector_allocation (
            allocation_date TEXT NOT NULL,
            sector TEXT NOT NULL,
            position_count INTEGER NOT NULL,
            market_value REAL NOT NULL,
            cost_basis REAL,
            unrealized_pnl REAL,
            daily_pnl REAL,
            account_weight_pct REAL NOT NULL,
            invested_weight_pct REAL,
            total_account_value REAL NOT NULL,
            updated_timestamp TEXT NOT NULL,
            PRIMARY KEY (allocation_date, sector)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sector_allocation_date ON portfolio_sector_allocation(allocation_date DESC)")


def load_data(conn, dashboard_date=None):
    if not table_exists(conn, "portfolio_dashboard"):
        raise RuntimeError("portfolio_dashboard does not exist. Run build_portfolio_dashboard_dataset.py first.")
    if not table_exists(conn, "company_universe"):
        raise RuntimeError("company_universe does not exist.")
    required_dashboard = {"dashboard_date", "asset_type", "ticker", "market_value", "cost_basis", "unrealized_pnl", "daily_pnl", "account_weight_pct", "invested_weight_pct", "total_account_value"}
    missing = required_dashboard - columns(conn, "portfolio_dashboard")
    if missing:
        raise RuntimeError("portfolio_dashboard missing columns: " + ", ".join(sorted(missing)))
    universe_columns = columns(conn, "company_universe")
    if not {"ticker", "sector"}.issubset(universe_columns):
        raise RuntimeError("company_universe must contain ticker and sector.")
    if dashboard_date is None:
        dashboard_date = conn.execute("SELECT MAX(dashboard_date) FROM portfolio_dashboard").fetchone()[0]
    if not dashboard_date:
        raise RuntimeError("portfolio_dashboard is empty.")
    query = """
        SELECT d.dashboard_date,
               COALESCE(NULLIF(TRIM(u.sector), ''), 'Unclassified') AS sector,
               d.ticker, d.market_value, d.cost_basis, d.unrealized_pnl,
               d.daily_pnl, d.account_weight_pct, d.invested_weight_pct,
               d.total_account_value
        FROM portfolio_dashboard d
        LEFT JOIN company_universe u ON UPPER(TRIM(u.ticker)) = UPPER(TRIM(d.ticker))
        WHERE d.dashboard_date = ? AND d.asset_type = 'SECURITY'
    """
    df = pd.read_sql_query(query, conn, params=(dashboard_date,))
    if df.empty:
        raise RuntimeError(f"No security rows found for {dashboard_date}.")
    return dashboard_date, df


def calculate(df):
    result = df.groupby("sector", as_index=False).agg(
        position_count=("ticker", "nunique"), market_value=("market_value", "sum"),
        cost_basis=("cost_basis", "sum"), unrealized_pnl=("unrealized_pnl", "sum"),
        daily_pnl=("daily_pnl", "sum"), account_weight_pct=("account_weight_pct", "sum"),
        invested_weight_pct=("invested_weight_pct", "sum"), total_account_value=("total_account_value", "max")
    )
    return result.sort_values("account_weight_pct", ascending=False)


def save(conn, date, df, timestamp, full_refresh):
    if full_refresh:
        conn.execute("DELETE FROM portfolio_sector_allocation WHERE allocation_date=?", (date,))
    rows = [(date, r.sector, int(r.position_count), float(r.market_value), float(r.cost_basis),
             float(r.unrealized_pnl), float(r.daily_pnl), float(r.account_weight_pct),
             float(r.invested_weight_pct), float(r.total_account_value), timestamp)
            for r in df.itertuples(index=False)]
    conn.executemany("""
        INSERT INTO portfolio_sector_allocation VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(allocation_date, sector) DO UPDATE SET
        position_count=excluded.position_count, market_value=excluded.market_value,
        cost_basis=excluded.cost_basis, unrealized_pnl=excluded.unrealized_pnl,
        daily_pnl=excluded.daily_pnl, account_weight_pct=excluded.account_weight_pct,
        invested_weight_pct=excluded.invested_weight_pct,
        total_account_value=excluded.total_account_value, updated_timestamp=excluded.updated_timestamp
    """, rows)


def main():
    p = argparse.ArgumentParser(description="Build portfolio sector allocation.")
    p.add_argument("--database", type=Path, default=DEFAULT_DB_PATH)
    p.add_argument("--dashboard-date")
    p.add_argument("--full-refresh", action="store_true")
    a = p.parse_args()
    db = a.database.resolve()
    if not db.exists(): raise FileNotFoundError(f"Database not found: {db}")
    with sqlite3.connect(db) as conn:
        ensure_table(conn)
        date, source = load_data(conn, a.dashboard_date)
        result = calculate(source)
        save(conn, date, result, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), a.full_refresh)
        conn.commit()
    print("\nPORTFOLIO SECTOR ALLOCATION COMPLETE")
    print(f"Date: {date} | Sectors: {len(result)}")
    print(result[["sector", "position_count", "market_value", "account_weight_pct", "unrealized_pnl"]].to_string(index=False, float_format=lambda x: f"{x:,.2f}"))


if __name__ == "__main__":
    main()
