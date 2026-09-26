import abc
import sqlite3

from datetime import datetime


class cursor(abc.ABC):
    """Common database-cursor interface for query execution."""

    @abc.abstractmethod
    def execute(self, query, params=()):
        """Execute a SQL statement."""

    @abc.abstractmethod
    def fetchone(self):
        """Fetch the next row from the result set."""

    @abc.abstractmethod
    def fetchall(self):
        """Fetch all remaining rows from the result set."""

    @abc.abstractmethod
    def commit(self):
        """Persist changes to the database."""

    @abc.abstractmethod
    def close(self):
        """Release resources used by the cursor."""


class SQLiteCursor(cursor):
    """Concrete sqlite3-backed cursor that implements the cursor interface."""

    def __init__(self, connection):
        self._connection = connection
        self._cursor = connection.cursor()

    def execute(self, query, params=()):
        return self._cursor.execute(query, params)

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def commit(self):
        self._connection.commit()

    def close(self):
        self._cursor.close()

    def __getattr__(self, name):
        return getattr(self._cursor, name)


# ===================================
# Database
# ===================================

conn = sqlite3.connect(
    "InvestmentAdvisor.db"
)

cursor = SQLiteCursor(conn)

# ===================================
# Get Latest Price
# ===================================

cursor.execute("""
SELECT DISTINCT ticker
FROM sec_financials
ORDER BY ticker
""")

tickers = [
    row[0]
    for row in cursor.fetchall()
]

updated = 0

for ticker in tickers:

    # -----------------------------
    # Latest Price
    # -----------------------------

    cursor.execute("""
    SELECT close_price
    FROM prices
    WHERE ticker = ?
    ORDER BY price_date DESC
    LIMIT 1
    """,
    (ticker,)
    )

    price_row = cursor.fetchone()

    if not price_row:

        continue

    current_price = price_row[0]

    # -----------------------------
    # Latest SEC Financials
    # -----------------------------

    cursor.execute("""
    SELECT
        fiscal_year,
        net_income,
        assets,
        liabilities
    FROM sec_financials
    WHERE ticker = ?
    ORDER BY fiscal_year DESC
    LIMIT 1
    """,
    (ticker,)
    )

    financials = cursor.fetchone()

    if not financials:

        continue

    fiscal_year = financials[0]
    net_income = financials[1]
    assets = financials[2]
    liabilities = financials[3]

    # -----------------------------
    # Equity
    # -----------------------------

    equity = None

    if (
        assets is not None
        and liabilities is not None
    ):

        equity = assets - liabilities

    # -----------------------------
    # Shares Outstanding
    # TEMPORARY PLACEHOLDER
    # -----------------------------

    shares_outstanding = 1000000000

    # Later we'll pull this from SEC.

    # -----------------------------
    # EPS
    # -----------------------------

    eps = None

    if (
        net_income is not None
        and shares_outstanding > 0
    ):

        eps = round(
            net_income
            / shares_outstanding,
            4
        )

    # -----------------------------
    # P/E Ratio
    # -----------------------------

    pe_ratio = None

    if (
        eps
        and eps > 0
    ):

        pe_ratio = round(
            current_price / eps,
            2
        )

    # -----------------------------
    # Book Value Per Share
    # -----------------------------

    book_value_per_share = None

    if (
        equity
        and shares_outstanding > 0
    ):

        book_value_per_share = round(
            equity
            / shares_outstanding,
            4
        )

    # -----------------------------
    # Price To Book
    # -----------------------------

    price_to_book = None

    if (
        book_value_per_share
        and book_value_per_share > 0
    ):

        price_to_book = round(
            current_price
            / book_value_per_share,
            2
        )

    # -----------------------------
    # Update Fundamentals
    # -----------------------------

    cursor.execute("""
    UPDATE fundamentals
    SET

        eps = ?,

        pe_ratio = ?,

        book_value_per_share = ?,

        price_to_book = ?,

        last_updated = ?

    WHERE ticker = ?
    """,
    (
        eps,
        pe_ratio,
        book_value_per_share,
        price_to_book,
        datetime.today().strftime(
            "%Y-%m-%d"
        ),
        ticker
    ))

    updated += 1

    print(
        f"{ticker} | "
        f"EPS={eps} | "
        f"PE={pe_ratio} | "
        f"P/B={price_to_book}"
    )

conn.commit()

conn.close()

print(
    f"\nUpdated {updated} companies"
)
