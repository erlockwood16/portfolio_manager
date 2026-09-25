import sqlite3
from abc import ABC, abstractmethod


class row(ABC):
    @property
    @abstractmethod
    def columns(self):
        raise NotImplementedError

    @abstractmethod
    def __getitem__(self, key):
        raise NotImplementedError

    @abstractmethod
    def __iter__(self):
        raise NotImplementedError

    @abstractmethod
    def __len__(self):
        raise NotImplementedError

    @abstractmethod
    def keys(self):
        raise NotImplementedError

    @abstractmethod
    def values(self):
        raise NotImplementedError

    @abstractmethod
    def items(self):
        raise NotImplementedError

    @abstractmethod
    def as_dict(self):
        raise NotImplementedError


class SQLiteRow(row):
    def __init__(self, values, columns):
        self._data = tuple(values)
        self._columns = tuple(columns)

    @property
    def columns(self):
        return self._columns

    def __getitem__(self, key):
        if isinstance(key, str):
            return self.as_dict()[key]
        return self._data[key]

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def keys(self):
        return list(self._columns)

    def values(self):
        return list(self._data)

    def items(self):
        return list(zip(self._columns, self._data))

    def as_dict(self):
        return dict(self.items())

    def __repr__(self):
        return repr(self.as_dict())


conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = conn.cursor()

ticker = input(
    "\nTicker: "
).upper()

cursor.execute("""
SELECT *

FROM investment_thesis

WHERE ticker = ?
""",
(ticker,)
)

raw_row = cursor.fetchone()

if not raw_row:

    print(
        f"No thesis found for {ticker}"
    )

    conn.close()
    exit()

columns = [
    "ticker",
    "bull_case",
    "bear_case",
    "key_risks",
    "catalysts",
    "fair_value",
    "target_position",
    "status",
    "last_updated",
]

the_row = SQLiteRow(raw_row, columns)

print("\n" + "=" * 80)
print("INVESTMENT THESIS")
print("=" * 80)

print(f"\nTicker: {the_row['ticker']}")

print(f"\nBull Case:\n{the_row['bull_case']}")

print(f"\nBear Case:\n{the_row['bear_case']}")

print(f"\nKey Risks:\n{the_row['key_risks']}")

print(f"\nCatalysts:\n{the_row['catalysts']}")

print(
    f"\nFair Value: "
    f"${the_row['fair_value']:.2f}"
)

print(
    f"\nTarget Position: "
    f"{the_row['target_position']}%"
)

print(
    f"\nStatus: "
    f"{the_row['status']}"
)

print(
    f"\nLast Updated: "
    f"{the_row['last_updated']}"
)

conn.close()
