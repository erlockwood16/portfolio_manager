import argparse
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT / "InvestmentAdvisor.db"

POSITION_HINTS = {
    "ticker", "symbol", "shares", "quantity", "current_quantity",
    "cost_basis", "average_cost", "avg_cost"
}


def quote_identifier(value):
    return '"' + value.replace('"', '""') + '"'


def table_names(connection):
    return [row[0] for row in connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()]


def columns(connection, table_name):
    return [row[1] for row in connection.execute(
        f"PRAGMA table_info({quote_identifier(table_name)})"
    ).fetchall()]


def row_count(connection, table_name):
    return connection.execute(
        f"SELECT COUNT(*) FROM {quote_identifier(table_name)}"
    ).fetchone()[0]


def preview(connection, table_name, table_columns):
    selected = [
        col for col in (
            "ticker", "symbol", "shares", "quantity", "current_quantity",
            "cost_basis", "total_cost_basis", "average_cost", "avg_cost",
            "market_value", "source", "broker"
        ) if col in table_columns
    ]
    if not selected:
        selected = table_columns[:8]
    if not selected:
        return [], []
    select_list = ", ".join(quote_identifier(col) for col in selected)
    rows = connection.execute(
        f"SELECT {select_list} FROM {quote_identifier(table_name)} LIMIT 25"
    ).fetchall()
    return selected, rows


def main():
    parser = argparse.ArgumentParser(
        description="Find the table where the Robinhood importer rebuilt open positions."
    )
    parser.add_argument("--database", type=Path, default=DEFAULT_DB_PATH)
    args = parser.parse_args()

    database_path = args.database.resolve()
    if not database_path.exists():
        raise FileNotFoundError(f"Database not found: {database_path}")

    candidates = []
    with sqlite3.connect(database_path) as connection:
        for table_name in table_names(connection):
            table_columns = columns(connection, table_name)
            lower_columns = {col.lower() for col in table_columns}
            count = row_count(connection, table_name)
            score = len(lower_columns & POSITION_HINTS)
            name_score = sum(
                token in table_name.lower()
                for token in ("position", "holding", "robinhood", "portfolio")
            )
            if score >= 2 or name_score > 0:
                candidates.append(
                    (score + name_score, table_name, count, table_columns)
                )

        candidates.sort(key=lambda item: (-item[0], abs(item[2] - 15), item[1]))

        print("\n" + "=" * 100)
        print("ROBINHOOD POSITION SOURCE DIAGNOSTIC")
        print("=" * 100)
        print(f"Database: {database_path}")
        print(f"{'Table':<42}{'Rows':>10}  Columns")
        print("-" * 100)
        for _, table_name, count, table_columns in candidates:
            print(f"{table_name:<42}{count:>10,}  {', '.join(table_columns)}")

        likely = [item for item in candidates if item[2] == 15]
        if not likely:
            likely = [item for item in candidates if item[2] > 0]

        if likely:
            _, table_name, count, table_columns = likely[0]
            selected, rows = preview(connection, table_name, table_columns)
            print("\n" + "=" * 100)
            print(f"MOST LIKELY ROBINHOOD POSITION TABLE: {table_name} ({count:,} rows)")
            print("=" * 100)
            print(" | ".join(selected))
            print("-" * 100)
            for row in rows:
                print(" | ".join("NULL" if value is None else str(value) for value in row))
            print("\nRun attribution against this source with:")
            print(
                "python portfolio/calculate_attribution.py "
                f"--positions-table {table_name} --full-refresh"
            )
        else:
            print("\nNo populated position-like table was found.")

        print("\nExplanation:")
        print("The importer reported 15 rebuilt positions, but it does not write them to the")
        print("legacy 'positions' table. The reset cleared only that legacy test table.")
        print("Use the populated Robinhood position table identified above as attribution input.")


if __name__ == "__main__":
    main()
