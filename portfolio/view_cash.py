import sqlite3
from abc import ABC, abstractmethod


class Row(ABC):
    """Base representation of a portfolio record."""

    @property
    @abstractmethod
    def source(self):
        """Return the source name for the record."""

    @property
    @abstractmethod
    def cash_balance(self):
        """Return the cash balance value."""

    @property
    @abstractmethod
    def last_updated(self):
        """Return the last update timestamp."""

    @abstractmethod
    def to_dict(self):
        """Serialize the row to a dictionary."""


class CashRow(Row):
    """Concrete cash row populated from the portfolio_cash table."""

    def __init__(self, source, cash_balance, last_updated):
        self._source = source
        self._cash_balance = float(cash_balance)
        self._last_updated = last_updated

    @property
    def source(self):
        return self._source

    @property
    def cash_balance(self):
        return self._cash_balance

    @property
    def last_updated(self):
        return self._last_updated

    def to_dict(self):
        return {
            "source": self.source,
            "cash_balance": self.cash_balance,
            "last_updated": self.last_updated,
        }

    def __iter__(self):
        yield self.source
        yield self.cash_balance
        yield self.last_updated

    def __str__(self):
        return f"{self.source}: ${self.cash_balance:,.2f} (updated {self.last_updated})"


def fetch_cash_rows():
    conn = sqlite3.connect("InvestmentAdvisor.db")
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                source,
                cash_balance,
                last_updated
            FROM portfolio_cash
            """
        )
        rows = cursor.fetchall()
        return [CashRow(source, cash_balance, last_updated) for source, cash_balance, last_updated in rows]
    finally:
        conn.close()


if __name__ == "__main__":
    rows = fetch_cash_rows()

    print("\nCASH BALANCE\n")
    for row in rows:
        print(f"{row.source}  ${row.cash_balance:,.2f}")

