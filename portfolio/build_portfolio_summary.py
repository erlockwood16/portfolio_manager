import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT / "InvestmentAdvisor.db"


def table_exists(conn, name):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def ensure_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_summary (
            summary_date TEXT PRIMARY KEY,
            position_count INTEGER NOT NULL,
            total_invested_value REAL NOT NULL,
            cash_balance REAL NOT NULL,
            total_account_value REAL NOT NULL,
            cash_weight_pct REAL NOT NULL,
            total_cost_basis REAL,
            unrealized_pnl REAL,
            unrealized_return_pct REAL,
            daily_pnl REAL,
            top_contributor TEXT,
            top_contributor_pnl REAL,
            top_detractor TEXT,
            top_detractor_pnl REAL,
            largest_position TEXT,
            largest_position_weight_pct REAL,
            top_5_weight_pct REAL,
            largest_sector TEXT,
            largest_sector_weight_pct REAL,
            concentration_level TEXT,
            updated_timestamp TEXT NOT NULL
        )
    """)


def load_dashboard(conn, date):
    if not table_exists(conn, "portfolio_dashboard"):
        raise RuntimeError("portfolio_dashboard does not exist.")
    if date is None:
        date = conn.execute("SELECT MAX(dashboard_date) FROM portfolio_dashboard").fetchone()[0]
    df = pd.read_sql_query("SELECT * FROM portfolio_dashboard WHERE dashboard_date=?", conn, params=(date,))
    if df.empty: raise RuntimeError(f"No dashboard rows found for {date}.")
    return date, df


def scalar_row(conn, table, date_column, date):
    if not table_exists(conn, table): return None
    return conn.execute(f'SELECT * FROM "{table}" WHERE "{date_column}"=?', (date,)).fetchone()


def calculate(conn, date, df):
    securities = df[df["asset_type"] == "SECURITY"].copy()
    cash = df[df["asset_type"] == "CASH"]
    if securities.empty or cash.empty: raise RuntimeError("Dashboard must contain security and cash rows.")
    top_contributor = securities.sort_values("daily_pnl", ascending=False).iloc[0]
    top_detractor = securities.sort_values("daily_pnl", ascending=True).iloc[0]
    largest = securities.sort_values("account_weight_pct", ascending=False).iloc[0]
    total_cost = float(securities["cost_basis"].sum())
    unrealized = float(securities["unrealized_pnl"].sum())
    concentration = None
    if table_exists(conn, "portfolio_concentration"):
        concentration = conn.execute("SELECT top_5_weight_pct, concentration_level FROM portfolio_concentration WHERE concentration_date=?", (date,)).fetchone()
    sector = None
    if table_exists(conn, "portfolio_sector_allocation"):
        sector = conn.execute("SELECT sector, account_weight_pct FROM portfolio_sector_allocation WHERE allocation_date=? ORDER BY account_weight_pct DESC LIMIT 1", (date,)).fetchone()
    return (
        date, len(securities), float(securities["market_value"].sum()), float(cash["market_value"].sum()),
        float(df["total_account_value"].max()), float(cash["account_weight_pct"].sum()), total_cost,
        unrealized, (unrealized / total_cost * 100 if total_cost else None),
        float(securities["daily_pnl"].sum(min_count=1)), str(top_contributor["ticker"]), float(top_contributor["daily_pnl"]),
        str(top_detractor["ticker"]), float(top_detractor["daily_pnl"]), str(largest["ticker"]),
        float(largest["account_weight_pct"]), concentration[0] if concentration else None,
        sector[0] if sector else None, sector[1] if sector else None,
        concentration[1] if concentration else None
    )


def save(conn, values, timestamp):
    conn.execute("""
        INSERT INTO portfolio_summary VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(summary_date) DO UPDATE SET
        position_count=excluded.position_count, total_invested_value=excluded.total_invested_value,
        cash_balance=excluded.cash_balance, total_account_value=excluded.total_account_value,
        cash_weight_pct=excluded.cash_weight_pct, total_cost_basis=excluded.total_cost_basis,
        unrealized_pnl=excluded.unrealized_pnl, unrealized_return_pct=excluded.unrealized_return_pct,
        daily_pnl=excluded.daily_pnl, top_contributor=excluded.top_contributor,
        top_contributor_pnl=excluded.top_contributor_pnl, top_detractor=excluded.top_detractor,
        top_detractor_pnl=excluded.top_detractor_pnl, largest_position=excluded.largest_position,
        largest_position_weight_pct=excluded.largest_position_weight_pct,
        top_5_weight_pct=excluded.top_5_weight_pct, largest_sector=excluded.largest_sector,
        largest_sector_weight_pct=excluded.largest_sector_weight_pct,
        concentration_level=excluded.concentration_level, updated_timestamp=excluded.updated_timestamp
    """, (*values, timestamp))


def main():
    p = argparse.ArgumentParser(description="Build consolidated portfolio summary.")
    p.add_argument("--database", type=Path, default=DEFAULT_DB_PATH)
    p.add_argument("--dashboard-date")
    a = p.parse_args()
    db = a.database.resolve()
    if not db.exists(): raise FileNotFoundError(f"Database not found: {db}")
    with sqlite3.connect(db) as conn:
        ensure_table(conn)
        date, df = load_dashboard(conn, a.dashboard_date)
        values = calculate(conn, date, df)
        save(conn, values, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        conn.commit()
        row = conn.execute("SELECT * FROM portfolio_summary WHERE summary_date=?", (date,)).fetchone()
        names = [x[0] for x in conn.execute("SELECT name FROM pragma_table_info('portfolio_summary')")]
    print("\nPORTFOLIO SUMMARY COMPLETE")
    for name, value in zip(names, row): print(f"{name}: {value}")


if __name__ == "__main__":
    main()
