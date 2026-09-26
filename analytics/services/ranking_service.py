from __future__ import annotations

import sqlite3
from datetime import datetime

import pandas as pd


def calculate_ranking_score(current_price: float, sma20: float) -> float:
    """Return the normalized screening score based on price relative to the 20-day SMA."""
    if sma20 == 0:
        return 0.0
    return (current_price / sma20) * 100


def calculate_ranking_scores(price_df: pd.DataFrame) -> pd.DataFrame:
    """Build a ranking score table from recent price history."""
    results: list[list[float | int | str]] = []

    for ticker in price_df["ticker"].unique():
        stock = price_df[price_df["ticker"] == ticker].sort_values("price_date")

        if len(stock) < 20:
            continue

        current_price = stock.iloc[-1]["close_price"]
        sma20 = stock["close_price"].tail(20).mean()

        ranking_score = calculate_ranking_score(current_price, sma20)
        results.append([ticker, current_price, sma20, ranking_score, ranking_score])

    columns = [
        "ticker",
        "current_price",
        "sma20",
        "momentum_score",
        "overall_score",
    ]

    return pd.DataFrame(results, columns=columns)


def update_screen_scores(conn: sqlite3.Connection, db_date: str | None = None) -> int:
    """Update the screen_scores table with price-relative momentum rankings."""
    query = """
        SELECT
            ticker,
            price_date,
            close_price
        FROM prices
    """

    price_df = pd.read_sql(query, conn)
    rankings = calculate_ranking_scores(price_df)

    updated = 0
    score_date = db_date or datetime.today().strftime("%Y-%m-%d")

    for row in rankings.itertuples(index=False):
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO screen_scores
            (
                ticker,
                momentum_score,
                overall_score,
                last_updated
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                row.ticker,
                row.momentum_score,
                row.overall_score,
                score_date,
            ),
        )
        updated += 1

    conn.commit()
    return updated


def run_ranking_update(db_path: str = "InvestmentAdvisor.db") -> int:
    """Open a SQLite database and refresh screen scores."""
    with sqlite3.connect(db_path) as conn:
        return update_screen_scores(conn)
