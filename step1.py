from abc import ABC, abstractmethod
import sqlite3


class table(ABC):
    @abstractmethod
    def create(self) -> None:
        """Create the underlying table if it does not exist."""

    @abstractmethod
    def insert(self, row: dict) -> None:
        """Insert a single row into the table."""

    @abstractmethod
    def fetch_all(self) -> list[dict]:
        """Fetch every row from the table."""

    @abstractmethod
    def update(self, where: dict, values: dict) -> int:
        """Update matching rows and return the number affected."""

    @abstractmethod
    def delete(self, where: dict) -> int:
        """Delete matching rows and return the number affected."""


class SQLiteTable(table):
    def __init__(self, conn: sqlite3.Connection, name: str, columns: list[str]):
        self.conn = conn
        self.name = name
        self.columns = columns

    def create(self) -> None:
        column_defs = ", ".join(f"{column} TEXT" for column in self.columns)
        self.conn.execute(f"CREATE TABLE IF NOT EXISTS {self.name} ({column_defs})")
        self.conn.commit()

    def insert(self, row: dict) -> None:
        if not row:
            raise ValueError("row cannot be empty")

        columns = ", ".join(row.keys())
        placeholders = ", ".join("?" for _ in row)
        values = tuple(row[key] for key in row)
        self.conn.execute(
            f"INSERT INTO {self.name} ({columns}) VALUES ({placeholders})",
            values,
        )
        self.conn.commit()

    def fetch_all(self) -> list[dict]:
        cursor = self.conn.execute(f"SELECT * FROM {self.name}")
        if cursor.description is None:
            return []

        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def update(self, where: dict, values: dict) -> int:
        if not where:
            raise ValueError("where conditions are required")
        if not values:
            raise ValueError("values to update are required")

        where_clause = " AND ".join(f"{key} = ?" for key in where)
        set_clause = ", ".join(f"{key} = ?" for key in values)
        params = tuple(values[key] for key in values) + tuple(where[key] for key in where)

        cursor = self.conn.execute(
            f"UPDATE {self.name} SET {set_clause} WHERE {where_clause}",
            params,
        )
        self.conn.commit()
        return cursor.rowcount

    def delete(self, where: dict) -> int:
        if not where:
            raise ValueError("where conditions are required")

        where_clause = " AND ".join(f"{key} = ?" for key in where)
        params = tuple(where[key] for key in where)

        cursor = self.conn.execute(
            f"DELETE FROM {self.name} WHERE {where_clause}",
            params,
        )
        self.conn.commit()
        return cursor.rowcount


if __name__ == "__main__":
    conn = sqlite3.connect("InvestmentAdvisor.db")
    table_obj = SQLiteTable(conn, "analytics_scores", ["ticker", "score", "date"])
    table_obj.create()
    table_obj.insert({"ticker": "AAPL", "score": "95", "date": "2025-09-25"})
    print(table_obj.fetch_all())
    print(table_obj.update({"ticker": "AAPL"}, {"score": "98"}))
    print(table_obj.delete({"ticker": "AAPL"}))
    conn.close()

import pandas as pd

conn = sqlite3.connect("InvestmentAdvisor.db")

for table in [
    "analytics_scores",
    "fundamentals",
    "prices"
\]:
    print(f"\n{table}")

    df = pd.read_sql(f"""
        SELECT
            ticker,
            COUNT(*) cnt
        FROM {table}
        GROUP BY ticker
        HAVING COUNT(*) > 1
        ORDER BY cnt DESC
    """, conn)

    print(df.head(20))

conn.close()