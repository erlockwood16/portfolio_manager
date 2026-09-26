import sqlite3
from abc import ABC, abstractmethod


class Row(ABC):
    """Abstract row wrapper for tabular data."""

    @property
    @abstractmethod
    def values(self):
        raise NotImplementedError

    @abstractmethod
    def __iter__(self):
        raise NotImplementedError

    @abstractmethod
    def __len__(self):
        raise NotImplementedError

    @abstractmethod
    def __getitem__(self, key):
        raise NotImplementedError

    @abstractmethod
    def to_dict(self):
        raise NotImplementedError


class RecommendedAllocationRow(Row):
    """Concrete row for the recommended_allocations table."""

    FIELD_NAMES = [
        "ticker",
        "overall_score",
        "allocation_pct",
        "position_value",
        "recommended_shares",
        "fair_value",
        "upside_pct",
    ]

    def __init__(self, values):
        self._values = tuple(values)

    @property
    def values(self):
        return self._values

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def __getitem__(self, key):
        if isinstance(key, str):
            return dict(zip(self.FIELD_NAMES, self._values))[key]
        return self._values[key]

    def to_dict(self):
        return dict(zip(self.FIELD_NAMES, self._values))

    def __str__(self):
        return str(self._values)


conn = sqlite3.connect("InvestmentAdvisor.db")
cursor = conn.cursor()

cursor.execute(
    """
    SELECT
        ticker,
        overall_score,
        allocation_pct,
        position_value,
        recommended_shares,
        fair_value,
        upside_pct
    FROM recommended_allocations
    ORDER BY allocation_pct DESC,
             overall_score DESC
    """
)

rows = [RecommendedAllocationRow(row) for row in cursor.fetchall()]

print("\n" + "=" * 100)
print("RECOMMENDED PORTFOLIO")
print("=" * 100)

for row in rows:
    print(
        f"{row[0]:<8}"
        f" Score={row[1]:6.1f}"
        f" Alloc={row[2]:5.1f}%"
        f" Value=${row[3]:10,.0f}"
        f" Shares={row[4]:8}"
        f" FairValue=${row[5]:10,.0f}"
        f" Upside={row[6]}%"
    )

conn.close()
