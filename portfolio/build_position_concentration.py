import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT / "InvestmentAdvisor.db"


def ensure_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_concentration (
            concentration_date TEXT PRIMARY KEY,
            position_count INTEGER NOT NULL,
            largest_position_ticker TEXT,
            largest_position_weight_pct REAL,
            top_3_weight_pct REAL NOT NULL,
            top_5_weight_pct REAL NOT NULL,
            top_10_weight_pct REAL NOT NULL,
            cash_weight_pct REAL NOT NULL,
            herfindahl_index REAL NOT NULL,
            effective_position_count REAL,
            concentration_level TEXT NOT NULL,
            total_account_value REAL NOT NULL,
            updated_timestamp TEXT NOT NULL
        )
    """)


def load_latest(conn, dashboard_date):
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='portfolio_dashboard'").fetchone()
    if not exists: raise RuntimeError("portfolio_dashboard does not exist.")
    if dashboard_date is None:
        dashboard_date = conn.execute("SELECT MAX(dashboard_date) FROM portfolio_dashboard").fetchone()[0]
    df = pd.read_sql_query("SELECT * FROM portfolio_dashboard WHERE dashboard_date=?", conn, params=(dashboard_date,))
    if df.empty: raise RuntimeError(f"No dashboard rows found for {dashboard_date}.")
    return dashboard_date, df


def calculate(date, df):
    positions = df[df["asset_type"] == "SECURITY"].copy().sort_values("account_weight_pct", ascending=False)
    if positions.empty: raise RuntimeError("No security positions found.")
    cash_rows = df[df["asset_type"] == "CASH"]
    cash_weight = float(cash_rows["account_weight_pct"].sum())
    weights = positions["account_weight_pct"].fillna(0).astype(float)
    hhi = float(((weights / 100.0) ** 2).sum())
    effective = (1.0 / hhi) if hhi > 0 else None
    top5 = float(weights.head(5).sum())
    level = "HIGH" if top5 >= 60 or weights.iloc[0] >= 20 else "MODERATE" if top5 >= 40 or weights.iloc[0] >= 10 else "LOW"
    return {
        "concentration_date": date, "position_count": len(positions),
        "largest_position_ticker": positions.iloc[0]["ticker"],
        "largest_position_weight_pct": float(weights.iloc[0]),
        "top_3_weight_pct": float(weights.head(3).sum()), "top_5_weight_pct": top5,
        "top_10_weight_pct": float(weights.head(10).sum()), "cash_weight_pct": cash_weight,
        "herfindahl_index": hhi, "effective_position_count": effective,
        "concentration_level": level, "total_account_value": float(df["total_account_value"].max())
    }


def save(conn, r, timestamp):
    conn.execute("""
        INSERT INTO portfolio_concentration VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(concentration_date) DO UPDATE SET
        position_count=excluded.position_count, largest_position_ticker=excluded.largest_position_ticker,
        largest_position_weight_pct=excluded.largest_position_weight_pct,
        top_3_weight_pct=excluded.top_3_weight_pct, top_5_weight_pct=excluded.top_5_weight_pct,
        top_10_weight_pct=excluded.top_10_weight_pct, cash_weight_pct=excluded.cash_weight_pct,
        herfindahl_index=excluded.herfindahl_index, effective_position_count=excluded.effective_position_count,
        concentration_level=excluded.concentration_level, total_account_value=excluded.total_account_value,
        updated_timestamp=excluded.updated_timestamp
    """, (*r.values(), timestamp))


def main():
    p = argparse.ArgumentParser(description="Build portfolio concentration metrics.")
    p.add_argument("--database", type=Path, default=DEFAULT_DB_PATH)
    p.add_argument("--dashboard-date")
    a = p.parse_args()
    db = a.database.resolve()
    if not db.exists(): raise FileNotFoundError(f"Database not found: {db}")
    with sqlite3.connect(db) as conn:
        ensure_table(conn)
        date, df = load_latest(conn, a.dashboard_date)
        result = calculate(date, df)
        save(conn, result, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        conn.commit()
    print("\nPORTFOLIO CONCENTRATION COMPLETE")
    for k, v in result.items(): print(f"{k}: {v:,.2f}" if isinstance(v, float) else f"{k}: {v}")


if __name__ == "__main__":
    main()
