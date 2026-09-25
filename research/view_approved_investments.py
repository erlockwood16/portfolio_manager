import sqlite3
from abc import ABC, abstractmethod


class row(ABC):
    def __init__(self, values, columns):
        self._values = tuple(values)
        self._columns = tuple(columns)

    @property
    def columns(self):
        return self._columns

    @property
    def values(self):
        return self._values

    @abstractmethod
    def __len__(self):
        return len(self._values)

    @abstractmethod
    def __iter__(self):
        return iter(self._values)

    @abstractmethod
    def __getitem__(self, key):
        if isinstance(key, str):
            return self._values[self._columns.index(key)]
        return self._values[key]

    @abstractmethod
    def __contains__(self, item):
        return item in self._values or item in self._columns

    @abstractmethod
    def as_dict(self):
        return dict(zip(self._columns, self._values))

    def keys(self):
        return self._columns

    def items(self):
        return self.as_dict().items()

    def __repr__(self):
        return f"row({self.as_dict()})"

    def __str__(self):
        return str(self.as_dict())


conn = sqlite3.connect("InvestmentAdvisor.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute(
    """
    SELECT
        ticker,
        fair_value,
        target_position_pct,
        status
    FROM investment_thesis
    WHERE status = 'APPROVED'
    ORDER BY target_position_pct DESC
    """
)

records = []
for db_row in cursor.fetchall():
    records.append(row(db_row, db_row.keys()))

print("\nAPPROVED INVESTMENTS\n")
for record in records:
    print(
        f"{record['ticker']:<8} "
        f"Fair Value=${record['fair_value']:.2f} "
        f"Target={record['target_position_pct']}%"
    )

conn.close()
