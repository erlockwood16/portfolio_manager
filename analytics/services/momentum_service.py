from __future__ import annotations

import sqlite3

import pandas as pd


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
