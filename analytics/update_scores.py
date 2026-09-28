import sqlite3
import pandas as pd
import numpy as np

from abc import ABC
from datetime import datetime


class momentum_score(ABC):
    """Calculate a simple trend-following score based on moving averages."""

    def __init__(
        self,
        volatility_weight: float = 0.50,
        max_volatility_penalty: float = 40,
    ):
        self.volatility_weight = volatility_weight
        self.max_volatility_penalty = max_volatility_penalty

    def calculate_momentum(
        self,
        current_price: float,
        sma20: float,
        sma50: float,
        sma200: float,
    ) -> float:
        momentum_score = 0

        if current_price > sma20:
            momentum_score += 30

        if current_price > sma50:
            momentum_score += 30

        if current_price > sma200:
            momentum_score += 40

        return round(float(momentum_score), 2)

    def calculate_volatility(self, close_prices: pd.Series) -> float:
        if close_prices.empty:
            return 0.0

        returns = close_prices.pct_change().fillna(0)
        volatility = returns.std(ddof=1) * np.sqrt(252) * 100

        if pd.isna(volatility):
            volatility = 0

        return round(float(volatility), 2)

    def calculate_overall(
        self,
        momentum_score: float,
        volatility: float,
    ) -> tuple[float, float]:
        volatility_penalty = min(
            volatility * self.volatility_weight,
            self.max_volatility_penalty,
        )

        raw_score = momentum_score - volatility_penalty

        return round(float(raw_score), 2), round(float(volatility_penalty), 2)

    def evaluate(
        self,
        close_prices: pd.Series,
        current_price: float,
        sma20: float,
        sma50: float,
        sma200: float,
    ) -> dict:
        momentum = self.calculate_momentum(
            current_price,
            sma20,
            sma50,
            sma200,
        )
        volatility = self.calculate_volatility(close_prices)
        overall_score, volatility_penalty = self.calculate_overall(
            momentum,
            volatility,
        )

        return {
            "momentum_score": momentum,
            "volatility": volatility,
            "volatility_penalty": volatility_penalty,
            "overall_score": overall_score,
            "raw_score": overall_score,
        }


class concrete_momentum_score(momentum_score):
    """Concrete implementation that uses the default scoring behavior."""

    pass


scorer = concrete_momentum_score()

# ========================================
# Cursor Wrapper
# ========================================

class cursor(ABC):
    """Abstract database cursor interface used by the analytics job."""

    def execute(self, query, parameters=()):
        raise NotImplementedError

    def fetchone(self):
        raise NotImplementedError

    def fetchall(self):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError


class sqlite_cursor(cursor):
    """Concrete SQLite-backed cursor implementation."""

    def __init__(self, connection):
        self._cursor = connection.cursor()

    def execute(self, query, parameters=()):
        return self._cursor.execute(query, parameters)

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def close(self):
        self._cursor.close()

    def __getattr__(self, name):
        return getattr(self._cursor, name)


# ========================================
# Connect Database
# ========================================

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = sqlite_cursor(conn)

# ========================================
# Load Price History
# ========================================

query = """
SELECT
    ticker,
    price_date,
    close_price
FROM prices
ORDER BY ticker, price_date
"""

df = pd.read_sql(
    query,
    conn
)

score_date = datetime.today().strftime(
    "%Y-%m-%d"
)

processed = 0
skipped = 0

# ========================================
# Universe Size
# ========================================

total_tickers = (
    df["ticker"]
    .nunique()
)

print(
    "\n" + "=" * 70
)

print(
    f"SCORING "
    f"{total_tickers:,} TICKERS"
)

print(
    "=" * 70
)

# ========================================
# Calculate Scores
# ========================================

for i, (ticker, stock) in enumerate(
    df.groupby("ticker"),
    start=1
):

    # ------------------------------------
    # Progress
    # ------------------------------------

    if i % 25 == 0 or i == total_tickers:

        print(
            f"Progress: "
            f"{i:,}/{total_tickers:,}"
        )

    stock = (
        stock
        .sort_values("price_date")
        .copy()
    )

    # ------------------------------------
    # Require SMA200
    # ------------------------------------

    if len(stock) < 200:

        skipped += 1

        continue

    # ====================================
    # Current Price
    # ====================================

    current_price = float(
        stock.iloc[-1]["close_price"]
    )

    # ====================================
    # Moving Averages
    # ====================================

    sma20 = float(
        stock["close_price"]
        .rolling(20)
        .mean()
        .iloc[-1]
    )

    sma50 = float(
        stock["close_price"]
        .rolling(50)
        .mean()
        .iloc[-1]
    )

    sma200 = float(
        stock["close_price"]
        .rolling(200)
        .mean()
        .iloc[-1]
    )

    # ====================================
    # Momentum Score
    # ====================================

    score_data = scorer.evaluate(
        close_prices=stock["close_price"],
        current_price=current_price,
        sma20=sma20,
        sma50=sma50,
        sma200=sma200,
    )

    momentum_score = score_data["momentum_score"]
    volatility = score_data["volatility"]
    volatility_penalty = score_data["volatility_penalty"]
    overall_score = score_data["overall_score"]
    raw_score = score_data["raw_score"]


    # ====================================
    # Save Scores
    # ====================================

    cursor.execute(
        """
        INSERT OR REPLACE INTO analytics_scores
(
    ticker,
    current_price,

    sma20,
    sma50,
    sma200,

    momentum_score,
    volatility,

    value_score,
    quality_score,
    growth_score,

    overall_score,

    score_date
)

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ticker,
            current_price,
            sma20,
            sma50,
            sma200,
            momentum_score,
            volatility,
            overall_score,
            score_date
        )
    )

    processed += 1

# ========================================
# Commit
# ========================================

conn.commit()

# ========================================
# Analytics Count
# ========================================

cursor.execute(
    """
    SELECT COUNT(*)
    FROM analytics_scores
    """
)

analytics_count = (
    cursor.fetchone()[0]
)

# ========================================
# Price Universe Count
# ========================================

cursor.execute(
    """
    SELECT COUNT(DISTINCT ticker)
    FROM prices
    """
)

price_universe = (
    cursor.fetchone()[0]
)

conn.close()

# ========================================
# Summary
# ========================================

print("\n" + "=" * 70)

print(
    "ANALYTICS SCORE UPDATE COMPLETE"
)

print("=" * 70)

print(
    f"\nProcessed Tickers : "
    f"{processed:,}"
)

print(
    f"Skipped Tickers   : "
    f"{skipped:,}"
)

print(
    f"Price Universe    : "
    f"{price_universe:,}"
)

print(
    f"Analytics Rows    : "
    f"{analytics_count:,}"
)

print("=" * 70)
