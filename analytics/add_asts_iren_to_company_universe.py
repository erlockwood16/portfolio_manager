import argparse
import sqlite3
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT / "InvestmentAdvisor.db"

SECURITIES = [
    ("ASTS", "AST SpaceMobile, Inc.", "Communication Services", "Wireless Telecommunication Services", "MANUAL"),
    ("IREN", "IREN Limited", "Information Technology", "IT Services", "MANUAL"),
]


def quote_identifier(value):
    return '"' + value.replace('"', '""') + '"'


def table_exists(connection, table_name):
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone() is not None


def table_columns(connection, table_name):
    return {
        row[1]: row
        for row in connection.execute(
            f"PRAGMA table_info({quote_identifier(table_name)})"
        ).fetchall()
    }


def ensure_company_universe(connection):
    if not table_exists(connection, "company_universe"):
        connection.execute(
            """
            CREATE TABLE company_universe (
                ticker TEXT PRIMARY KEY,
                company_name TEXT NOT NULL,
                sector TEXT,
                industry TEXT,
                source TEXT NOT NULL,
                date_added TEXT
            )
            """
        )

    columns = table_columns(connection, "company_universe")
    required_existing = {"ticker", "company_name", "sector", "industry", "source"}
    missing = required_existing - set(columns)
    if missing:
        raise RuntimeError(
            "company_universe is missing required columns: "
            + ", ".join(sorted(missing))
        )

    # Safely migrate older schemas that do not yet contain date_added.
    if "date_added" not in columns:
        connection.execute(
            "ALTER TABLE company_universe ADD COLUMN date_added TEXT"
        )
        print("Added missing company_universe.date_added column.")

    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_company_universe_ticker
        ON company_universe (ticker)
        """
    )


def upsert_securities(connection, date_added):
    connection.executemany(
        """
        INSERT INTO company_universe (
            ticker, company_name, sector, industry, source, date_added
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker) DO UPDATE SET
            company_name = excluded.company_name,
            sector = excluded.sector,
            industry = excluded.industry,
            source = excluded.source,
            date_added = COALESCE(company_universe.date_added, excluded.date_added)
        """,
        [(*security, date_added) for security in SECURITIES],
    )


def remove_redundant_overrides(connection):
    if not table_exists(connection, "asset_classification_overrides"):
        return 0
    cursor = connection.execute(
        """
        DELETE FROM asset_classification_overrides
        WHERE UPPER(TRIM(ticker)) IN ('ASTS', 'IREN')
        """
    )
    return cursor.rowcount


def validate_results(connection):
    rows = connection.execute(
        """
        SELECT ticker, company_name, sector, industry, source, date_added
        FROM company_universe
        WHERE UPPER(TRIM(ticker)) IN ('ASTS', 'IREN')
        ORDER BY ticker
        """
    ).fetchall()
    if len(rows) != 2:
        raise RuntimeError(
            f"Expected 2 company_universe rows after upsert, but found {len(rows)}."
        )
    return rows


def print_summary(database_path, rows, overrides_removed):
    print("\n" + "=" * 112)
    print("COMPANY UNIVERSE UPDATE COMPLETE")
    print("=" * 112)
    print(f"Database: {database_path}")
    print(f"Redundant overrides removed: {overrides_removed:,}")
    print()
    print(
        f"{'Ticker':<8}{'Company Name':<28}{'Sector':<27}"
        f"{'Industry':<40}{'Source':<10}Date Added"
    )
    print("-" * 112)
    for ticker, company_name, sector, industry, source, date_added in rows:
        print(
            f"{ticker:<8}{company_name:<28}{sector:<27}"
            f"{industry:<40}{source:<10}{date_added or 'N/A'}"
        )
    print("=" * 112)
    print("\nNext run:")
    print(r"python .\analytics\build_asset_classification.py --full-refresh")
    print(r"python .\portfolio\build_sector_allocation.py --full-refresh")
    print(r"python .\portfolio\build_portfolio_summary.py")


def main():
    parser = argparse.ArgumentParser(
        description="Add ASTS and IREN to company_universe and migrate date_added if needed."
    )
    parser.add_argument("--database", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--date-added", default=date.today().isoformat())
    parser.add_argument("--keep-overrides", action="store_true")
    args = parser.parse_args()

    try:
        datetime.strptime(args.date_added, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("--date-added must use YYYY-MM-DD format.") from exc

    database_path = args.database.resolve()
    if not database_path.exists():
        raise FileNotFoundError(f"Database not found: {database_path}")

    with sqlite3.connect(database_path) as connection:
        ensure_company_universe(connection)
        upsert_securities(connection, args.date_added)
        overrides_removed = 0 if args.keep_overrides else remove_redundant_overrides(connection)
        rows = validate_results(connection)
        connection.commit()

    print_summary(database_path, rows, overrides_removed)


if __name__ == "__main__":
    main()
