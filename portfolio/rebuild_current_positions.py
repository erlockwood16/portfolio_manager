import argparse
import csv
import re
import sqlite3
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT / "InvestmentAdvisor.db"
BROKER_SOURCE = "ROBINHOOD"
EPSILON = 1e-6
OPTION_OPEN_CODES = {"BTO"}
OPTION_CLOSE_CODES = {"STC"}
OPTION_EXPIRATION_CODES = {"OEXP", "EXP", "EXPIRE", "EXPIRED"}


def parse_number(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text or text in {"-", "--"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    text = re.sub(r"[$,%(),]", "", text).strip()
    try:
        number = float(text)
    except ValueError:
        return None
    return -number if negative else number


def parse_option_quantity(value):
    """Parse Robinhood option quantities, including expiration values such as 2S or 6S."""
    if value is None:
        return None
    text = str(value).strip().upper()
    if not text or text in {"-", "--"}:
        return None
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text.replace(",", ""))
    return float(match.group(0)) if match else None


def parse_date(value):
    text = str(value or "").strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    raise ValueError(f"Unsupported activity date: {text!r}")


def normalize_ticker(value):
    return str(value or "").strip().upper().replace(".", "-")


def normalize_contract(description):
    """Return one canonical key for BTO, STC, and Robinhood expiration descriptions."""
    text = re.sub(r"\s+", " ", str(description or "")).strip()
    text = re.sub(r"^Option Expiration for\s+", "", text, flags=re.IGNORECASE)

    pattern = re.compile(
        r"^(?P<ticker>.+?)\s+"
        r"(?P<date>\d{1,2}/\d{1,2}/\d{4})\s+"
        r"(?P<type>Call|Put)\s+\$?(?P<strike>[\d,]+(?:\.\d+)?)$",
        flags=re.IGNORECASE,
    )
    match = pattern.match(text)
    if not match:
        return text

    ticker = re.sub(r"\s+", " ", match.group("ticker")).strip().upper()
    expiration = parse_date(match.group("date")).strftime("%m/%d/%Y")
    option_type = match.group("type").title()
    strike = float(match.group("strike").replace(",", ""))
    return f"{ticker} {expiration} {option_type} ${strike:.2f}"


def contract_expiration(contract):
    match = re.search(r"\b(\d{2}/\d{2}/\d{4})\s+(?:Call|Put)\b", contract, flags=re.IGNORECASE)
    return datetime.strptime(match.group(1), "%m/%d/%Y") if match else None


def read_activity(csv_path, same_day_order="file"):
    rows = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "Activity Date", "Instrument", "Description", "Trans Code",
            "Quantity", "Price", "Amount",
        }
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV is missing required columns: {sorted(missing)}")

        for sequence, raw in enumerate(reader):
            try:
                activity_date = parse_date(raw.get("Activity Date"))
            except ValueError:
                continue
            rows.append({
                "sequence": sequence,
                "activity_date": activity_date,
                "ticker": normalize_ticker(raw.get("Instrument")),
                "description": str(raw.get("Description") or "").strip(),
                "code": str(raw.get("Trans Code") or "").strip().upper(),
                "quantity": parse_number(raw.get("Quantity")),
                "option_quantity": parse_option_quantity(raw.get("Quantity")),
                "price": parse_number(raw.get("Price")),
                "amount": parse_number(raw.get("Amount")),
            })

    multiplier = -1 if same_day_order == "reverse" else 1
    return sorted(rows, key=lambda r: (r["activity_date"], multiplier * r["sequence"]))


def consume_stock_fifo(lots, quantity, sale_date, sale_proceeds):
    remaining = quantity
    realized = []
    while remaining > EPSILON and lots:
        lot = lots[0]
        used = min(remaining, lot["shares_remaining"])
        proceeds = sale_proceeds * used / quantity
        cost_basis = used * lot["cost_per_share"]
        realized.append({
            "ticker": lot["ticker"], "purchase_date": lot["purchase_date"],
            "sale_date": sale_date, "shares_sold": used,
            "cost_per_share": lot["cost_per_share"], "sale_price": proceeds / used,
            "cost_basis": cost_basis, "proceeds": proceeds,
            "realized_gain_loss": proceeds - cost_basis,
        })
        lot["shares_remaining"] -= used
        remaining -= used
        if lot["shares_remaining"] <= EPSILON:
            lots.popleft()
    return realized, remaining


def rebuild_stock_lots(rows):
    by_ticker = defaultdict(deque)
    all_lots, realized, warnings = [], [], []
    for row in rows:
        if row["code"] not in {"BUY", "SELL"}:
            continue
        ticker = row["ticker"]
        quantity = abs(row["quantity"] or 0.0)
        if not ticker or quantity <= EPSILON:
            continue
        trade_date = row["activity_date"].strftime("%Y-%m-%d")
        if row["code"] == "BUY":
            cash = abs(row["amount"]) if row["amount"] is not None else quantity * abs(row["price"] or 0.0)
            lot = {
                "ticker": ticker, "purchase_date": trade_date,
                "original_shares": quantity, "shares_remaining": quantity,
                "cost_per_share": cash / quantity, "original_cost_basis": cash,
                "source_sequence": row["sequence"],
            }
            by_ticker[ticker].append(lot)
            all_lots.append(lot)
        else:
            proceeds = abs(row["amount"]) if row["amount"] is not None else quantity * abs(row["price"] or 0.0)
            matches, unmatched = consume_stock_fifo(by_ticker[ticker], quantity, trade_date, proceeds)
            realized.extend(matches)
            if unmatched > EPSILON:
                warnings.append(f"{ticker}: sale exceeds tracked buys by {unmatched:.6f} shares on {trade_date}")
    return [lot for lot in all_lots if lot["shares_remaining"] > EPSILON], realized, warnings


def aggregate_positions(open_lots, realized_lots):
    realized_by_ticker = defaultdict(float)
    for row in realized_lots:
        realized_by_ticker[row["ticker"]] += row["realized_gain_loss"]
    grouped = defaultdict(list)
    for lot in open_lots:
        grouped[lot["ticker"]].append(lot)
    positions = []
    for ticker, lots in sorted(grouped.items()):
        shares = sum(x["shares_remaining"] for x in lots)
        cost = sum(x["shares_remaining"] * x["cost_per_share"] for x in lots)
        if shares > EPSILON:
            positions.append((ticker, shares, cost / shares, cost, realized_by_ticker[ticker]))
    return positions


def consume_option_fifo(lots, quantity, proceeds):
    remaining = quantity
    removed_cost = 0.0
    matched_proceeds = 0.0
    while remaining > EPSILON and lots:
        lot = lots[0]
        used = min(remaining, lot["contracts_remaining"])
        removed_cost += used * lot["cost_per_contract"]
        matched_proceeds += proceeds * used / quantity if quantity else 0.0
        lot["contracts_remaining"] -= used
        remaining -= used
        if lot["contracts_remaining"] <= EPSILON:
            lots.popleft()
    return removed_cost, matched_proceeds, remaining


def calculate_option_results(rows):
    """Handle BTO to STC, explicit OEXP, and inferred expiration through the file as-of date."""
    lots = defaultdict(deque)
    realized_events = []
    warnings = []
    as_of_date = max((row["activity_date"] for row in rows), default=None)

    for row in rows:
        code = row["code"]
        if code not in OPTION_OPEN_CODES | OPTION_CLOSE_CODES | OPTION_EXPIRATION_CODES:
            continue
        contract = normalize_contract(row["description"])
        quantity = abs(row["option_quantity"] or 0.0)
        event_date = row["activity_date"].strftime("%Y-%m-%d")
        if not contract or quantity <= EPSILON:
            warnings.append(
                f"Option row skipped because contract or quantity could not be parsed: "
                f"code={code}, description={row['description']!r}, quantity={row['quantity']!r}"
            )
            continue

        if code in OPTION_OPEN_CODES:
            premium = abs(row["amount"]) if row["amount"] is not None else quantity * abs(row["price"] or 0.0) * 100
            lots[contract].append({
                "open_date": event_date,
                "contracts_remaining": quantity,
                "cost_per_contract": premium / quantity,
            })
            continue

        event_type = "EXPIRATION" if code in OPTION_EXPIRATION_CODES else "CLOSE"
        proceeds = 0.0 if event_type == "EXPIRATION" else abs(row["amount"] or 0.0)
        removed_cost, matched_proceeds, unmatched = consume_option_fifo(lots[contract], quantity, proceeds)
        matched = quantity - unmatched
        if matched > EPSILON:
            realized_events.append({
                "contract_description": contract, "event_date": event_date,
                "event_type": event_type, "contracts_closed": matched,
                "cost_basis": removed_cost, "proceeds": matched_proceeds,
                "realized_gain_loss": matched_proceeds - removed_cost,
            })
        if unmatched > EPSILON:
            warnings.append(f"Option {contract}: {event_type.lower()} exceeds tracked opens by {unmatched:g} contracts")

    # Robinhood exports may omit an OEXP row. Any remaining long option whose
    # expiration date is on or before the latest activity date is expired at $0.
    if as_of_date is not None:
        for contract, contract_lots in lots.items():
            expiration = contract_expiration(contract)
            if expiration is None or expiration.date() > as_of_date.date():
                continue
            contracts = sum(x["contracts_remaining"] for x in contract_lots)
            cost = sum(x["contracts_remaining"] * x["cost_per_contract"] for x in contract_lots)
            if contracts > EPSILON:
                realized_events.append({
                    "contract_description": contract,
                    "event_date": expiration.strftime("%Y-%m-%d"),
                    "event_type": "EXPIRATION",
                    "contracts_closed": contracts,
                    "cost_basis": cost,
                    "proceeds": 0.0,
                    "realized_gain_loss": -cost,
                })
                for lot in contract_lots:
                    lot["contracts_remaining"] = 0.0
                warnings.append(f"Option {contract}: inferred expiration at zero proceeds")

    open_options = []
    for contract, contract_lots in sorted(lots.items()):
        contracts = sum(x["contracts_remaining"] for x in contract_lots)
        cost = sum(x["contracts_remaining"] * x["cost_per_contract"] for x in contract_lots)
        if contracts > EPSILON:
            open_options.append((contract, contracts, cost))
    return realized_events, open_options, warnings


def table_exists(cursor, name):
    cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cursor.fetchone() is not None


def preserve_other_brokers(cursor):
    if not table_exists(cursor, "portfolio_positions"):
        return []
    columns = {r[1] for r in cursor.execute("PRAGMA table_info(portfolio_positions)").fetchall()}
    fields = []
    for name, fallback in (
        ("ticker", "NULL"), ("shares", "0"), ("average_cost", "NULL"),
        ("total_cost_basis", "NULL"), ("realized_gain_loss", "NULL"),
        ("source", "'UNKNOWN'"), ("last_updated", "datetime('now')"),
    ):
        fields.append(name if name in columns else f"{fallback} AS {name}")
    where = "WHERE UPPER(COALESCE(source,'')) <> 'ROBINHOOD'" if "source" in columns else ""
    return cursor.execute(f"SELECT {', '.join(fields)} FROM portfolio_positions {where}").fetchall()


def recreate_tables(cursor):
    preserved = preserve_other_brokers(cursor)
    cursor.execute("DROP TABLE IF EXISTS portfolio_positions_new")
    cursor.execute("""
        CREATE TABLE portfolio_positions_new (
            ticker TEXT NOT NULL, shares REAL NOT NULL, average_cost REAL,
            total_cost_basis REAL, realized_gain_loss REAL, source TEXT NOT NULL,
            last_updated TEXT NOT NULL, PRIMARY KEY (ticker, source)
        )
    """)
    if preserved:
        cursor.executemany("INSERT OR REPLACE INTO portfolio_positions_new VALUES (?, ?, ?, ?, ?, ?, COALESCE(?, datetime('now')))", preserved)
    cursor.execute("DROP TABLE IF EXISTS portfolio_positions")
    cursor.execute("ALTER TABLE portfolio_positions_new RENAME TO portfolio_positions")

    cursor.execute("DROP TABLE IF EXISTS portfolio_lots")
    cursor.execute("""
        CREATE TABLE portfolio_lots (
            lot_id INTEGER PRIMARY KEY AUTOINCREMENT, ticker TEXT NOT NULL,
            purchase_date TEXT NOT NULL, original_shares REAL NOT NULL,
            shares_remaining REAL NOT NULL, cost_per_share REAL NOT NULL,
            original_cost_basis REAL NOT NULL, remaining_cost_basis REAL NOT NULL,
            source_sequence INTEGER, source TEXT NOT NULL, last_updated TEXT NOT NULL
        )
    """)
    cursor.execute("DROP TABLE IF EXISTS realized_stock_lots")
    cursor.execute("""
        CREATE TABLE realized_stock_lots (
            realized_lot_id INTEGER PRIMARY KEY AUTOINCREMENT, ticker TEXT NOT NULL,
            purchase_date TEXT NOT NULL, sale_date TEXT NOT NULL, shares_sold REAL NOT NULL,
            cost_per_share REAL NOT NULL, sale_price REAL NOT NULL, cost_basis REAL NOT NULL,
            proceeds REAL NOT NULL, realized_gain_loss REAL NOT NULL, source TEXT NOT NULL,
            last_updated TEXT NOT NULL
        )
    """)
    cursor.execute("DROP TABLE IF EXISTS option_open_positions")
    cursor.execute("CREATE TABLE option_open_positions (contract_description TEXT PRIMARY KEY, contracts REAL NOT NULL, cost_basis REAL NOT NULL, calculated_date TEXT NOT NULL)")
    cursor.execute("DROP TABLE IF EXISTS option_realized_events")
    cursor.execute("""
        CREATE TABLE option_realized_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT, contract_description TEXT NOT NULL,
            event_date TEXT NOT NULL, event_type TEXT NOT NULL, contracts_closed REAL NOT NULL,
            cost_basis REAL NOT NULL, proceeds REAL NOT NULL, realized_gain_loss REAL NOT NULL,
            calculated_date TEXT NOT NULL
        )
    """)
    cursor.execute("DROP TABLE IF EXISTS option_realized_pnl")
    cursor.execute("CREATE TABLE option_realized_pnl (contract_description TEXT PRIMARY KEY, realized_gain_loss REAL NOT NULL, calculated_date TEXT NOT NULL)")
    cursor.execute("CREATE TABLE IF NOT EXISTS watchlist (ticker TEXT PRIMARY KEY)")


def save_results(db, open_lots, realized_lots, positions, option_events, open_options, timestamp):
    with sqlite3.connect(db) as conn:
        cur = conn.cursor()
        recreate_tables(cur)
        cur.executemany("""
            INSERT INTO portfolio_lots
            (ticker,purchase_date,original_shares,shares_remaining,cost_per_share,
             original_cost_basis,remaining_cost_basis,source_sequence,source,last_updated)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, [(x["ticker"], x["purchase_date"], x["original_shares"], x["shares_remaining"], x["cost_per_share"], x["original_cost_basis"], x["shares_remaining"] * x["cost_per_share"], x["source_sequence"], BROKER_SOURCE, timestamp) for x in open_lots])
        cur.executemany("""
            INSERT INTO realized_stock_lots
            (ticker,purchase_date,sale_date,shares_sold,cost_per_share,sale_price,
             cost_basis,proceeds,realized_gain_loss,source,last_updated)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, [(x["ticker"], x["purchase_date"], x["sale_date"], x["shares_sold"], x["cost_per_share"], x["sale_price"], x["cost_basis"], x["proceeds"], x["realized_gain_loss"], BROKER_SOURCE, timestamp) for x in realized_lots])
        cur.executemany("INSERT OR REPLACE INTO portfolio_positions (ticker,shares,average_cost,total_cost_basis,realized_gain_loss,source,last_updated) VALUES (?,?,?,?,?,?,?)", [(t, s, a, c, r, BROKER_SOURCE, timestamp) for t, s, a, c, r in positions])
        cur.executemany("INSERT INTO option_open_positions VALUES (?,?,?,?)", [(c, n, cost, timestamp) for c, n, cost in open_options])
        cur.executemany("""
            INSERT INTO option_realized_events
            (contract_description,event_date,event_type,contracts_closed,cost_basis,
             proceeds,realized_gain_loss,calculated_date) VALUES (?,?,?,?,?,?,?,?)
        """, [(x["contract_description"], x["event_date"], x["event_type"], x["contracts_closed"], x["cost_basis"], x["proceeds"], x["realized_gain_loss"], timestamp) for x in option_events])
        totals = defaultdict(float)
        for x in option_events:
            totals[x["contract_description"]] += x["realized_gain_loss"]
        cur.executemany("INSERT INTO option_realized_pnl VALUES (?,?,?)", [(c, p, timestamp) for c, p in totals.items()])
        cur.executemany("INSERT OR IGNORE INTO watchlist(ticker) VALUES (?)", [(x[0],) for x in positions])
        conn.commit()


def main():
    parser = argparse.ArgumentParser(description="Rebuild Robinhood positions with FIFO lots and option expirations.")
    parser.add_argument("csv_file", type=Path)
    parser.add_argument("--database", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--same-day-order", choices=("file", "reverse"), default="file")
    args = parser.parse_args()

    csv_path = args.csv_file.resolve()
    db_path = args.database.resolve()
    if not csv_path.exists():
        raise FileNotFoundError(f"Activity CSV not found: {csv_path}")
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    rows = read_activity(csv_path, args.same_day_order)
    open_lots, realized_lots, stock_warnings = rebuild_stock_lots(rows)
    positions = aggregate_positions(open_lots, realized_lots)
    option_events, open_options, option_warnings = calculate_option_results(rows)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_results(db_path, open_lots, realized_lots, positions, option_events, open_options, timestamp)

    expirations = [x for x in option_events if x["event_type"] == "EXPIRATION"]
    closes = [x for x in option_events if x["event_type"] == "CLOSE"]
    warnings = stock_warnings + option_warnings
    print("\n" + "=" * 76)
    print("V2 LOT-BASED POSITION REBUILD COMPLETE")
    print("=" * 76)
    print(f"Activity rows read          : {len(rows):,}")
    print(f"Open stock/ETF positions    : {len(positions):,}")
    print(f"Open stock/ETF lots         : {len(open_lots):,}")
    print(f"Realized stock lot matches  : {len(realized_lots):,}")
    print(f"Open option positions       : {len(open_options):,}")
    print(f"Option close events         : {len(closes):,}")
    print(f"Option expiration events    : {len(expirations):,}")
    print(f"Expiration losses           : ${sum(x['realized_gain_loss'] for x in expirations):,.2f}")
    print(f"Total realized option P/L   : ${sum(x['realized_gain_loss'] for x in option_events):,.2f}")
    print(f"Warnings                    : {len(warnings):,}")
    print("=" * 76)
    for warning in warnings[:30]:
        print(f"WARNING: {warning}")
    print("\nExpiration handling assumes expired long options have zero proceeds.")
    print("Assignments, exercises, STO/BTC short options, and live unrealized option P/L require separate handling.")


if __name__ == "__main__":
    main()
