import argparse
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT / "InvestmentAdvisor.db"
DEFAULT_IMPORTER = ROOT / "portfolio" / "import_robinhood_transactions.py"
DEFAULT_POSITIONS_TABLE = "positions"


def quote_identifier(value):
    return '"' + value.replace('"', '""') + '"'


def table_exists(connection, table_name):
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone() is not None


def table_columns(connection, table_name):
    return [
        row[1]
        for row in connection.execute(
            f"PRAGMA table_info({quote_identifier(table_name)})"
        ).fetchall()
    ]


def row_count(connection, table_name):
    return connection.execute(
        f"SELECT COUNT(*) FROM {quote_identifier(table_name)}"
    ).fetchone()[0]


def preview_positions(connection, table_name):
    columns = table_columns(connection, table_name)
    preferred = [
        column
        for column in (
            "ticker", "symbol", "quantity", "shares", "current_quantity",
            "cost_basis", "total_cost_basis", "average_cost", "avg_cost",
            "source", "broker", "account_name"
        )
        if column in columns
    ]
    selected = preferred or columns[:8]
    if not selected:
        return [], []
    select_list = ", ".join(quote_identifier(column) for column in selected)
    rows = connection.execute(
        f"SELECT {select_list} FROM {quote_identifier(table_name)} LIMIT 25"
    ).fetchall()
    return selected, rows


def create_table_backup(connection, table_name, backup_table):
    connection.execute(
        f"CREATE TABLE {quote_identifier(backup_table)} AS "
        f"SELECT * FROM {quote_identifier(table_name)}"
    )


def print_rows(title, columns, rows):
    print("\n" + title)
    print("=" * 90)
    if not rows:
        print("No rows found.")
        return
    print(" | ".join(columns))
    print("-" * 90)
    for row in rows:
        print(" | ".join("NULL" if value is None else str(value) for value in row))


def run_robinhood_importer(importer_path, database_path):
    command = [sys.executable, str(importer_path)]
    print("\nRunning Robinhood importer:")
    print(" ".join(command))
    print(
        "\nIMPORTANT: the importer must use this database: "
        f"{database_path}\n"
        "If the importer has its own DB_PATH constant, confirm it points to the same file."
    )
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"Robinhood importer failed with exit code {result.returncode}. "
            "The original positions remain available in the SQL backup table and database backup file."
        )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Back up and clear the current positions table, then rebuild it using "
            "the Robinhood transaction importer."
        )
    )
    parser.add_argument("--database", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--importer", type=Path, default=DEFAULT_IMPORTER)
    parser.add_argument("--positions-table", default=DEFAULT_POSITIONS_TABLE)
    parser.add_argument(
        "--confirm-reset",
        action="store_true",
        help="Required confirmation before deleting current position rows.",
    )
    parser.add_argument(
        "--skip-import",
        action="store_true",
        help="Clear positions without running the Robinhood importer.",
    )
    args = parser.parse_args()

    database_path = args.database.resolve()
    importer_path = args.importer.resolve()
    positions_table = args.positions_table.strip()

    if not database_path.exists():
        raise FileNotFoundError(f"Database not found: {database_path}")
    if not positions_table:
        raise ValueError("A positions table name is required.")
    if not args.skip_import and not importer_path.exists():
        raise FileNotFoundError(f"Robinhood importer not found: {importer_path}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_backup = database_path.with_name(
        f"{database_path.stem}_before_positions_reset_{timestamp}{database_path.suffix}"
    )
    backup_table = f"{positions_table}_backup_{timestamp}"

    with sqlite3.connect(database_path) as connection:
        if not table_exists(connection, positions_table):
            raise RuntimeError(
                f"Positions table '{positions_table}' does not exist. "
                "Run the Robinhood importer directly so it can create/rebuild the table."
            )
        before_count = row_count(connection, positions_table)
        columns, rows = preview_positions(connection, positions_table)
        print_rows("CURRENT POSITIONS BEFORE RESET", columns, rows)
        print(f"\nCurrent row count: {before_count:,}")

    if not args.confirm_reset:
        print("\nNO CHANGES MADE.")
        print("Review the rows above. To reset and rebuild from Robinhood, run:")
        print(
            "python portfolio/reset_robinhood_positions.py --confirm-reset"
        )
        return

    shutil.copy2(database_path, file_backup)
    print(f"\nDatabase file backup created: {file_backup.name}")

    with sqlite3.connect(database_path) as connection:
        create_table_backup(connection, positions_table, backup_table)
        connection.execute(f"DELETE FROM {quote_identifier(positions_table)}")
        connection.commit()
        cleared_count = row_count(connection, positions_table)
        if cleared_count != 0:
            raise RuntimeError("Positions table was not fully cleared.")
        print(f"SQL backup table created: {backup_table}")
        print(f"Cleared {before_count:,} row(s) from {positions_table}.")

    if not args.skip_import:
        run_robinhood_importer(importer_path, database_path)

    with sqlite3.connect(database_path) as connection:
        after_count = row_count(connection, positions_table)
        columns, rows = preview_positions(connection, positions_table)
        print_rows("POSITIONS AFTER ROBINHOOD REBUILD", columns, rows)

    print("\n" + "=" * 90)
    print("ROBINHOOD POSITION RESET COMPLETE")
    print("=" * 90)
    print(f"Database:             {database_path}")
    print(f"Rows before reset:    {before_count:,}")
    print(f"Rows after rebuild:   {after_count:,}")
    print(f"Database backup:      {file_backup.name}")
    print(f"SQL backup table:     {backup_table}")
    print("=" * 90)

    if not args.skip_import and after_count == 0:
        raise RuntimeError(
            "The importer completed but positions is still empty. Check that the importer "
            "uses the same InvestmentAdvisor.db and that the newest Robinhood CSV was found."
        )

    print("\nNext run:")
    print("python portfolio/calculate_attribution.py --full-refresh")


if __name__ == "__main__":
    main()
