import sqlite3
from abc import ABC, abstractmethod


class Row(ABC):
    @property
    @abstractmethod
    def ticker(self):
        """Ticker symbol for the row."""

    @property
    @abstractmethod
    def eps(self):
        """Earnings per share."""

    @property
    @abstractmethod
    def pe_ratio(self):
        """Price-to-earnings ratio."""

    @property
    @abstractmethod
    def book_value_per_share(self):
        """Book value per share."""

    @property
    @abstractmethod
    def price_to_book(self):
        """Price-to-book ratio."""

    @abstractmethod
    def as_tuple(self):
        """Return the underlying row data as a tuple."""

    @abstractmethod
    def __iter__(self):
        """Allow iteration over the row data."""

    @abstractmethod
    def __len__(self):
        """Return the row length."""

    @abstractmethod
    def __getitem__(self, index):
        """Index into the row data."""

    def __str__(self):
        return (
            f"{self.ticker:<8}"
            f"EPS={self.eps}  "
            f"PE={self.pe_ratio}  "
            f"BVPS={self.book_value_per_share}  "
            f"P/B={self.price_to_book}"
        )


class MarketMetricsRow(Row):
    def __init__(self, values):
        self._values = tuple(values)

    @property
    def ticker(self):
        return self._values[0]

    @property
    def eps(self):
        return self._values[1]

    @property
    def pe_ratio(self):
        return self._values[2]

    @property
    def book_value_per_share(self):
        return self._values[3]

    @property
    def price_to_book(self):
        return self._values[4]

    def as_tuple(self):
        return self._values

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def __getitem__(self, index):
        return self._values[index]


conn = sqlite3.connect("InvestmentAdvisor.db")
cursor = conn.cursor()

cursor.execute(
    """
SELECT
    ticker,
    eps,
    pe_ratio,
    book_value_per_share,
    price_to_book
FROM fundamentals
ORDER BY ticker
"""
)

rows = [MarketMetricsRow(row) for row in cursor.fetchall()]

print("\nMARKET METRICS\n")

for row in rows:
    print(str(row))

conn.close()
