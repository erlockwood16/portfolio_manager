import argparse
import csv
import hashlib
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "InvestmentAdvisor.db"
DEFAULT_IMPORT_FOLDER = ROOT / "portfolio" / "imports"
SOURCE_NAME = "ROBINHOOD"

STOCK_BUY_CODES = {"BUY"}
STOCK_SELL_CODES = {"SELL"}
DIVIDEND_CODES = {"CDIV", "MDIV"}
CASH_TRANSFER_CODES = {"ACH", "DCF"}
EXCLUDED_CODES = {
    "BTO", "STC", "STO", "BTC", "OEXP", "OASGN",
    "SLIP", "FUTSWP"
}


def clean_text(value):
    return "" if value is None else str(value).strip()


def normalize_code(value):
    return clean_text(value).upper()


def parse_date(value):
    value = clean_text(value)
    if not value:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    raise ValueError(f"Unsupported date format: {value}")


def parse_number(value):
    value = clean_text(value)
    if not value:
        return None
    negative = value.startswith("(") and value.endswith(")")
    cleaned = (value.replace("$", "").replace(",", "")
                    .replace("(", "").replace(")", "").strip())
    if not cleaned:
        return None
    number = float(cleaned)
    return -number if negative else number


def make_transaction_hash(activity_date, process_date, settle_date, ticker,
                          description, transaction_code, quantity, price, amount):
    parts = [activity_date, process_date, settle_date, ticker, description,
             transaction_code, quantity, price, amount]
    raw = "|".join("" if value is None else str(value) for value in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_tables(cursor):
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS robinhood_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transaction_hash TEXT NOT NULL UNIQUE,
        activity_date TEXT,
        process_date TEXT,
        settle_date TEXT,
        ticker TEXT,
        description TEXT,
        transaction_code TEXT,
        transaction_type TEXT,
        quantity REAL,
        price REAL,
        amount REAL,
        source TEXT NOT NULL,
        imported_at TEXT NOT NULL
    )
    """)
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_robinhood_transactions_ticker
    ON robinhood_transactions (ticker)
    """)
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_robinhood_transactions_date
    ON robinhood_transactions (activity_date)
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS robinhood_cash_ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transaction_hash TEXT NOT NULL UNIQUE,
        transaction_date TEXT NOT NULL,
        ticker TEXT,
        cash_type TEXT NOT NULL,
        description TEXT,
        amount REAL NOT NULL,
        source TEXT NOT NULL,
        imported_at TEXT NOT NULL
    )
    """)
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_robinhood_cash_ledger_date
    ON robinhood_cash_ledger (transaction_date)
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS portfolio_positions (
        ticker TEXT PRIMARY KEY,
        shares REAL NOT NULL,
        average_cost REAL,
        total_cost_basis REAL,
        source TEXT NOT NULL,
        last_updated TEXT NOT NULL
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS portfolio_cash (
        source TEXT PRIMARY KEY,
        cash_balance REAL NOT NULL,
        last_updated TEXT NOT NULL
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS import_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        file_name TEXT NOT NULL,
        imported_at TEXT NOT NULL,
        stock_rows_imported INTEGER NOT NULL,
        cash_rows_imported INTEGER NOT NULL,
        duplicate_rows INTEGER NOT NULL,
        excluded_rows INTEGER NOT NULL,
        error_rows INTEGER NOT NULL
    )
    """)


def classify_transaction(row):
    ticker = clean_text(row.get("Instrument")).upper()
    description = clean_text(row.get("Description"))
    code = normalize_code(row.get("Trans Code"))
    quantity = parse_number(row.get("Quantity"))
    price = parse_number(row.get("Price"))
    amount = parse_number(row.get("Amount"))

    if code in STOCK_BUY_CODES and ticker:
        return {
            "category": "STOCK", "transaction_type": "BUY", "ticker": ticker,
            "quantity": abs(quantity) if quantity is not None else None,
            "price": abs(price) if price is not None else None,
            "amount": amount, "cash_type": "STOCK_PURCHASE"
        }

    if code in STOCK_SELL_CODES and ticker:
        return {
            "category": "STOCK", "transaction_type": "SELL", "ticker": ticker,
            "quantity": abs(quantity) if quantity is not None else None,
            "price": abs(price) if price is not None else None,
            "amount": amount, "cash_type": "STOCK_SALE"
        }

    if code in DIVIDEND_CODES:
        return {
            "category": "CASH", "transaction_type": "DIVIDEND",
            "ticker": ticker or None, "quantity": None, "price": None,
            "amount": amount, "cash_type": "DIVIDEND"
        }

    if code in CASH_TRANSFER_CODES:
        description_upper = description.upper()
        if (amount is not None and amount < 0) or "WITHDRAWAL" in description_upper:
            cash_type = "WITHDRAWAL"
            amount = -abs(amount) if amount is not None else None
        else:
            cash_type = "DEPOSIT"
            amount = abs(amount) if amount is not None else None
        return {
            "category": "CASH", "transaction_type": cash_type,
            "ticker": None, "quantity": None, "price": None,
            "amount": amount, "cash_type": cash_type
        }

    if code in EXCLUDED_CODES:
        return None
    return None


def insert_transaction(cursor, row, classification, imported_at):
    activity_date = parse_date(row.get("Activity Date"))
    process_date = parse_date(row.get("Process Date"))
    settle_date = parse_date(row.get("Settle Date"))
    description = clean_text(row.get("Description"))
    transaction_code = normalize_code(row.get("Trans Code"))

    unique_hash = make_transaction_hash(
        activity_date, process_date, settle_date, classification["ticker"],
        description, transaction_code, classification["quantity"],
        classification["price"], classification["amount"]
    )

    cursor.execute("""
    INSERT OR IGNORE INTO robinhood_transactions (
        transaction_hash, activity_date, process_date, settle_date, ticker,
        description, transaction_code, transaction_type, quantity, price,
        amount, source, imported_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        unique_hash, activity_date, process_date, settle_date,
        classification["ticker"], description, transaction_code,
        classification["transaction_type"], classification["quantity"],
        classification["price"], classification["amount"], SOURCE_NAME,
        imported_at
    ))
    return cursor.rowcount == 1, unique_hash, activity_date, description


def insert_cash_ledger_entry(cursor, unique_hash, transaction_date,
                             classification, description, imported_at):
    amount = classification["amount"]
    if amount is None or transaction_date is None:
        return False
    cursor.execute("""
    INSERT OR IGNORE INTO robinhood_cash_ledger (
        transaction_hash, transaction_date, ticker, cash_type, description,
        amount, source, imported_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        unique_hash, transaction_date, classification["ticker"],
        classification["cash_type"], description, amount, SOURCE_NAME,
        imported_at
    ))
    return cursor.rowcount == 1


def rebuild_positions(cursor):
    cursor.execute("DELETE FROM portfolio_positions WHERE source = ?", (SOURCE_NAME,))
    cursor.execute("""
    SELECT ticker, transaction_type, quantity, price, amount
    FROM robinhood_transactions
    WHERE source = ? AND transaction_type IN ('BUY', 'SELL')
    ORDER BY activity_date, id
    """, (SOURCE_NAME,))

    positions = {}
    for ticker, transaction_type, quantity, price, amount in cursor.fetchall():
        quantity = quantity or 0.0
        position = positions.setdefault(ticker, {"shares": 0.0, "cost_basis": 0.0})

        if transaction_type == "BUY":
            purchase_cost = quantity * price if price is not None else abs(amount or 0.0)
            position["shares"] += quantity
            position["cost_basis"] += purchase_cost
        else:
            existing_shares = position["shares"]
            if existing_shares > 0:
                average_cost = position["cost_basis"] / existing_shares
                shares_sold = min(quantity, existing_shares)
                position["cost_basis"] -= shares_sold * average_cost
            position["shares"] -= quantity
            if abs(position["shares"]) < 0.0000001:
                position["shares"] = 0.0
                position["cost_basis"] = 0.0

    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    saved = 0
    for ticker, position in positions.items():
        shares = position["shares"]
        if shares <= 0.0000001:
            continue
        total_cost = max(position["cost_basis"], 0.0)
        average_cost = total_cost / shares
        cursor.execute("""
        INSERT OR REPLACE INTO portfolio_positions (
            ticker, shares, average_cost, total_cost_basis, source, last_updated
        ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            ticker, round(shares, 8), round(average_cost, 6),
            round(total_cost, 2), SOURCE_NAME, updated_at
        ))
        saved += 1
    return saved


def rebuild_cash_balance(cursor):
    cursor.execute("""
    SELECT COALESCE(SUM(amount), 0)
    FROM robinhood_cash_ledger
    WHERE source = ?
    """, (SOURCE_NAME,))
    balance = round(cursor.fetchone()[0], 2)
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
    INSERT OR REPLACE INTO portfolio_cash (source, cash_balance, last_updated)
    VALUES (?, ?, ?)
    """, (SOURCE_NAME, balance, updated_at))
    return balance


def import_robinhood_csv(csv_path, replace_existing=False):
    csv_path = Path(csv_path).resolve()
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        create_tables(cursor)
        if replace_existing:
            cursor.execute("DELETE FROM robinhood_cash_ledger WHERE source = ?", (SOURCE_NAME,))
            cursor.execute("DELETE FROM robinhood_transactions WHERE source = ?", (SOURCE_NAME,))
            cursor.execute("DELETE FROM portfolio_positions WHERE source = ?", (SOURCE_NAME,))
            cursor.execute("DELETE FROM portfolio_cash WHERE source = ?", (SOURCE_NAME,))

        imported_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        stock_count = cash_count = duplicate_count = excluded_count = error_count = 0

        with open(csv_path, "r", encoding="utf-8-sig", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            required = {
                "Activity Date", "Process Date", "Settle Date", "Instrument",
                "Description", "Trans Code", "Quantity", "Price", "Amount"
            }
            missing = required - set(reader.fieldnames or [])
            if missing:
                raise ValueError("Robinhood CSV is missing columns: " + ", ".join(sorted(missing)))

            for row_number, row in enumerate(reader, start=2):
                if None in row or not any(clean_text(v) for v in row.values()):
                    excluded_count += 1
                    continue
                try:
                    classification = classify_transaction(row)
                    if classification is None:
                        excluded_count += 1
                        continue
                    inserted, unique_hash, activity_date, description = insert_transaction(
                        cursor, row, classification, imported_at
                    )
                    if not inserted:
                        duplicate_count += 1
                        continue

                    if classification["category"] == "STOCK":
                        stock_count += 1
                    if insert_cash_ledger_entry(
                        cursor, unique_hash, activity_date, classification,
                        description, imported_at
                    ):
                        cash_count += 1
                except Exception as exc:
                    error_count += 1
                    print(f"Row {row_number} skipped: {exc}")

        positions_saved = rebuild_positions(cursor)
        cash_balance = rebuild_cash_balance(cursor)

        cursor.execute("""
        INSERT INTO import_history (
            source, file_name, imported_at, stock_rows_imported,
            cash_rows_imported, duplicate_rows, excluded_rows, error_rows
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            SOURCE_NAME, csv_path.name, imported_at, stock_count, cash_count,
            duplicate_count, excluded_count, error_count
        ))
        conn.commit()

        print("\n" + "=" * 70)
        print("ROBINHOOD STOCK AND CASH IMPORT COMPLETE")
        print("=" * 70)
        print(f"File: {csv_path.name}")
        print(f"Stock transactions imported: {stock_count}")
        print(f"Cash ledger entries imported: {cash_count}")
        print(f"Duplicate rows skipped: {duplicate_count}")
        print(f"Excluded rows skipped: {excluded_count}")
        print(f"Error rows skipped: {error_count}")
        print(f"Open positions rebuilt: {positions_saved}")
        print(f"Calculated Robinhood cash: ${cash_balance:,.2f}")

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Import Robinhood stock and cash transactions into InvestmentAdvisor.db"
    )
    parser.add_argument("csv_file", nargs="?", help="Path to Robinhood transaction-history CSV")
    parser.add_argument(
        "--replace", action="store_true",
        help="Delete prior Robinhood imports before loading this CSV"
    )
    return parser.parse_args()


def main():
    args = parse_arguments()
    if args.csv_file:
        csv_path = Path(args.csv_file)
    else:
        DEFAULT_IMPORT_FOLDER.mkdir(parents=True, exist_ok=True)
        csv_files = sorted(DEFAULT_IMPORT_FOLDER.glob("*.csv"))
        if not csv_files:
            print("\nNo CSV supplied.")
            print("Run with a path, or place a CSV in:")
            print(DEFAULT_IMPORT_FOLDER)
            sys.exit(1)
        csv_path = csv_files[-1]
        print(f"\nUsing latest CSV found:\n{csv_path}")

    import_robinhood_csv(csv_path, replace_existing=args.replace)


if __name__ == "__main__":
    main()
