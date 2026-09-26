from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd


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
