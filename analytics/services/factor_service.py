from __future__ import annotations

import sqlite3
from datetime import datetime

import numpy as np
import pandas as pd


def calculate_value_score(pe_ratio: float) -> int:
    """Convert a P/E ratio into a 0-100 value score."""
    if pe_ratio <= 15:
        return 100
    if pe_ratio <= 25:
        return 80
    if pe_ratio <= 35:
        return 60
    if pe_ratio <= 50:
        return 40
    return 20


def calculate_quality_score(roe: float, debt_to_equity: float) -> int:
    """Combine profitability and leverage into a single quality score."""
    quality_score = 0

    if roe >= 20:
        quality_score += 50
    elif roe >= 10:
        quality_score += 25

    if debt_to_equity <= 0.5:
        quality_score += 50
    elif debt_to_equity <= 1.0:
        quality_score += 25

    return quality_score


def calculate_growth_score(revenue_growth: float, earnings_growth: float) -> int:
    """Average growth across revenue and earnings into a 0-100 score."""
    avg_growth = (revenue_growth + earnings_growth) / 2

    if avg_growth >= 30:
        return 100
    if avg_growth >= 20:
        return 80
    if avg_growth >= 10:
        return 60
    if avg_growth >= 5:
        return 40
    return 20


def calculate_overall_score(
    value_score: int,
    quality_score: int,
    growth_score: int,
    momentum_score: float,
) -> float:
    """Blend factor scores into a final composite score."""
    return round(
        (value_score * 0.30)
        + (quality_score * 0.30)
        + (growth_score * 0.20)
        + (momentum_score * 0.20),
        2,
    )


def update_factor_scores(conn: sqlite3.Connection) -> int:
    """Update analytics scores for all fundamentals rows in the database."""
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            ticker,
            pe_ratio,
            revenue_growth,
            earnings_growth,
            debt_to_equity,
            roe
        FROM fundamentals
        """
    )
    rows = cursor.fetchall()

    updated = 0

    for row in rows:
        ticker = row[0]
        pe_ratio = row[1]
        revenue_growth = row[2]
        earnings_growth = row[3]
        debt_to_equity = row[4]
        roe = row[5]

        if any(value is None for value in (pe_ratio, revenue_growth, earnings_growth, debt_to_equity, roe)):
            print(f"Skipping {ticker}: missing one or more factor inputs")
            continue

        value_score = calculate_value_score(pe_ratio)
        quality_score = calculate_quality_score(roe, debt_to_equity)
        growth_score = calculate_growth_score(revenue_growth, earnings_growth)

        cursor.execute(
            """
            SELECT momentum_score
            FROM analytics_scores
            WHERE ticker = ?
            """,
            (ticker,),
        )
        momentum_row = cursor.fetchone()

        if not momentum_row:
            print(f"No analytics found for {ticker}")
            continue

        momentum_score = momentum_row[0]
        overall_score = calculate_overall_score(
            value_score,
            quality_score,
            growth_score,
            momentum_score,
        )

        cursor.execute(
            """
            UPDATE analytics_scores
            SET
                value_score = ?,
                quality_score = ?,
                growth_score = ?,
                overall_score = ?,
                calculated_date = ?
            WHERE ticker = ?
            """,
            (
                value_score,
                quality_score,
                growth_score,
                overall_score,
                datetime.today().strftime("%Y-%m-%d"),
                ticker,
            ),
        )

        updated += 1
        print(
            f"{ticker} | "
            f"Value={value_score} | "
            f"Quality={quality_score} | "
            f"Growth={growth_score} | "
            f"Overall={overall_score}"
        )

    conn.commit()
    return updated


def run_update(db_path: str = "InvestmentAdvisor.db") -> int:
    """Open a SQLite database and refresh factor scores."""
    with sqlite3.connect(db_path) as conn:
        return update_factor_scores(conn)




def calculate_momentum_factor_score(
    current_price: float,
    sma20: float,
    sma50: float,
    sma200: float,
) -> int:
    """Score momentum by comparing the latest price to key moving averages."""
    momentum_score = 0

    if current_price > sma20:
        momentum_score += 30

    if current_price > sma50:
        momentum_score += 30

    if current_price > sma200:
        momentum_score += 40

    return momentum_score


def calculate_momentum_scores(price_df: pd.DataFrame) -> pd.DataFrame:
    """Build a momentum score table for all tickers with enough price history."""
    results: list[list[float | int | str]] = []

    for ticker in price_df["ticker"].unique():
        stock = price_df[price_df["ticker"] == ticker].sort_values("price_date")

        if len(stock) < 200:
            continue

        current_price = stock.iloc[-1]["close_price"]
        sma20 = stock["close_price"].rolling(20).mean().iloc[-1]
        sma50 = stock["close_price"].rolling(50).mean().iloc[-1]
        sma200 = stock["close_price"].rolling(200).mean().iloc[-1]

        results.append(
            [
                ticker,
                current_price,
                sma20,
                sma50,
                sma200,
                calculate_momentum_factor_score(
                    current_price,
                    sma20,
                    sma50,
                    sma200,
                ),
            ]
        )

    columns = [
        "ticker",
        "current_price",
        "sma20",
        "sma50",
        "sma200",
        "momentum_score",
    ]

    return pd.DataFrame(results, columns=columns)


def calculate_momentum_scores_from_db(db_path: str = "InvestmentAdvisor.db") -> pd.DataFrame:
    """Load price history from SQLite and return momentum scores."""
    query = """
        SELECT
            ticker,
            price_date,
            close_price
        FROM prices
        ORDER BY ticker, price_date
    """

    with sqlite3.connect(db_path) as conn:
        price_df = pd.read_sql(query, conn)

    return calculate_momentum_scores(price_df)


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


def calculate_volatility(stock: pd.DataFrame) -> float:
    """Return annualized volatility for a ticker's price history."""
    if len(stock) < 30:
        return 0.0

    stock = stock.copy()
    stock["returns"] = stock["close_price"].pct_change()
    volatility = stock["returns"].std() * np.sqrt(252) * 100
    return round(float(volatility), 2)


def calculate_volatility_scores(price_df: pd.DataFrame) -> pd.DataFrame:
    """Build a volatility table for all tickers with enough price history."""
    results: list[list[float | int | str]] = []

    for ticker in price_df["ticker"].unique():
        stock = price_df[price_df["ticker"] == ticker].sort_values("price_date")
        volatility = calculate_volatility(stock)

        if len(stock) < 30 or volatility == 0.0:
            continue

        results.append([ticker, volatility])

    return pd.DataFrame(results, columns=["ticker", "volatility"])


def calculate_volatility_scores_from_db(db_path: str = "InvestmentAdvisor.db") -> pd.DataFrame:
    """Load prices from SQLite and return annualized volatility by ticker."""
    query = """
        SELECT
            ticker,
            price_date,
            close_price
        FROM prices
        ORDER BY ticker, price_date
    """

    with sqlite3.connect(db_path) as conn:
        price_df = pd.read_sql(query, conn)

    return calculate_volatility_scores(price_df)


if __name__ == "__main__":
    print(f"\nUpdated {run_update()} stocks")
