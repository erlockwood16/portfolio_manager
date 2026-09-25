import sqlite3
from abc import ABC, abstractmethod


class row(ABC):
    @property
    @abstractmethod
    def ticker(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def revenue_growth(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def earnings_growth(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def debt_to_equity(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def roe(self):
        raise NotImplementedError

    @abstractmethod
    def display_line(self):
        raise NotImplementedError


class SecDerivedMetricsRow(row):
    def __init__(self, ticker, revenue_growth, earnings_growth, debt_to_equity, roe):
        self._ticker = ticker
        self._revenue_growth = revenue_growth
        self._earnings_growth = earnings_growth
        self._debt_to_equity = debt_to_equity
        self._roe = roe

    @property
    def ticker(self):
        return self._ticker

    @property
    def revenue_growth(self):
        return self._revenue_growth

    @property
    def earnings_growth(self):
        return self._earnings_growth

    @property
    def debt_to_equity(self):
        return self._debt_to_equity

    @property
    def roe(self):
        return self._roe

    def display_line(self):
        return (
            f"{self.ticker:<8}"
            f"Revenue Growth={self.revenue_growth}%  "
            f"Earnings Growth={self.earnings_growth}%  "
            f"D/E={self.debt_to_equity}  "
            f"ROE={self.roe}%"
        )

    @classmethod
    def from_db_row(cls, db_row):
        return cls(*db_row)


conn = sqlite3.connect("InvestmentAdvisor.db")
cursor = conn.cursor()

cursor.execute(
    """
SELECT
    ticker,
    revenue_growth,
    earnings_growth,
    debt_to_equity,
    roe
FROM fundamentals
ORDER BY ticker
"""
)

rows = [SecDerivedMetricsRow.from_db_row(row) for row in cursor.fetchall()]

print("\nSEC DERIVED METRICS\n")
for item in rows:
    print(item.display_line())

conn.close()
