import sqlite3
from abc import ABC, abstractmethod


class Cursor(ABC):
    """Abstract DB-API-like cursor contract."""

    @abstractmethod
    def execute(self, sql, parameters=()):
        raise NotImplementedError

    @abstractmethod
    def executemany(self, sql, seq_of_parameters):
        raise NotImplementedError

    @abstractmethod
    def fetchone(self):
        raise NotImplementedError

    @abstractmethod
    def fetchmany(self, size=None):
        raise NotImplementedError

    @abstractmethod
    def fetchall(self):
        raise NotImplementedError

    @abstractmethod
    def close(self):
        raise NotImplementedError


class SqliteCursor(Cursor):
    """Concrete implementation backed by sqlite3's cursor."""

    def __init__(self, connection):
        self._cursor = connection.cursor()

    def execute(self, sql, parameters=()):
        self._cursor.execute(sql, parameters)
        return self

    def executemany(self, sql, seq_of_parameters):
        self._cursor.executemany(sql, seq_of_parameters)
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchmany(self, size=None):
        if size is None:
            size = self._cursor.arraysize
        return self._cursor.fetchmany(size)

    def fetchall(self):
        return self._cursor.fetchall()

    def close(self):
        self._cursor.close()

    @property
    def description(self):
        return self._cursor.description

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    def __iter__(self):
        return iter(self._cursor)


if __name__ == "__main__":
    conn = sqlite3.connect("InvestmentAdvisor.db")
    cursor = SqliteCursor(conn)

    cursor.execute(
        """
        SELECT
            ticker,
            fiscal_year,
            shares_outstanding
        FROM sec_financials
        ORDER BY ticker,
                 fiscal_year DESC
        """
    )

    rows = cursor.fetchall()

    print("\nSHARES OUTSTANDING\n")
    for row in rows:
        print(
            f"{row[0]:<8}"
            f"FY{row[1]}  "
            f"Shares={row[2]}"
        )

    cursor.close()
    conn.close()
