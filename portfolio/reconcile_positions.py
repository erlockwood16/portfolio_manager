import argparse
import csv
import re
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "InvestmentAdvisor.db"
SOURCE = "ROBINHOOD"
SHARE_TOLERANCE = 0.000001
COST_TOLERANCE = 0.01

ALIASES = {
    "ticker": ["ticker", "symbol", "instrument"],
    "shares": ["shares", "quantity", "qty", "current shares"],
    "average_cost": ["average cost", "average_cost", "avg cost", "avg_cost", "cost per share"],
    "total_cost_basis": ["total cost basis", "total_cost_basis", "cost basis", "cost_basis"],
    "market_value": ["market value", "market_value", "equity", "current value"],
}


def parse_number(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"-", "--", "n/a", "none"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    text = re.sub(r"[$,%(),]", "", text).strip()
    try:
        number = float(text)
    except ValueError:
        return None
    return -number if negative else number


def normalize_ticker(value):
    return str(value or "").strip().upper().replace(".", "-")


def normalized_header(value):
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def resolve_columns(fieldnames):
    actual = {normalized_header(name): name for name in (fieldnames or [])}
    resolved = {}
    for canonical, candidates in ALIASES.items():
        for candidate in candidates:
            if candidate in actual:
                resolved[canonical] = actual[candidate]
                break
    missing = {"ticker", "shares"} - set(resolved)
    if missing:
        raise ValueError(
            "Holdings CSV must contain ticker/symbol and shares/quantity columns. "
            f"Missing: {sorted(missing)}; found: {fieldnames}"
        )
    if "average_cost" not in resolved and "total_cost_basis" not in resolved:
        raise ValueError(
            "Holdings CSV must contain either average cost or total cost basis."
        )
    return resolved


def read_current_holdings(csv_path):
    holdings = {}
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = resolve_columns(reader.fieldnames)
        for row_number, row in enumerate(reader, start=2):
            ticker = normalize_ticker(row.get(columns["ticker"]))
            shares = parse_number(row.get(columns["shares"]))
            if not ticker or shares is None or shares <= SHARE_TOLERANCE:
                continue
            average_cost = (
                parse_number(row.get(columns["average_cost"]))
                if "average_cost" in columns else None
            )
            total_cost = (
                parse_number(row.get(columns["total_cost_basis"]))
                if "total_cost_basis" in columns else None
            )
            market_value = (
                parse_number(row.get(columns["market_value"]))
                if "market_value" in columns else None
            )
            if total_cost is None and average_cost is not None:
                total_cost = shares * average_cost
            if average_cost is None and total_cost is not None and shares:
                average_cost = total_cost / shares
            if ticker in holdings:
                prior = holdings[ticker]
                combined_shares = prior["shares"] + shares
                combined_cost = prior["total_cost_basis"] + total_cost
                holdings[ticker] = {
                    "ticker": ticker,
                    "shares": combined_shares,
                    "average_cost": combined_cost / combined_shares,
                    "total_cost_basis": combined_cost,
                    "market_value": (prior.get("market_value") or 0) + (market_value or 0),
                }
            else:
                holdings[ticker] = {
                    "ticker": ticker,
                    "shares": shares,
                    "average_cost": average_cost,
                    "total_cost_basis": total_cost,
                    "market_value": market_value,
                }
    return holdings


def load_database_positions(connection):
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        SELECT ticker, shares, average_cost, total_cost_basis, source, last_updated
        FROM portfolio_positions
        WHERE UPPER(COALESCE(source, '')) = ?
        """,
        (SOURCE,),
    ).fetchall()
    return {normalize_ticker(row["ticker"]): dict(row) for row in rows}


def latest_prices(connection):
    rows = connection.execute(
        """
        WITH ranked AS (
            SELECT ticker, close_price, price_date,
                   ROW_NUMBER() OVER (
                       PARTITION BY ticker
                       ORDER BY price_date DESC, rowid DESC
                   ) AS rn
            FROM prices
        )
        SELECT ticker, close_price, price_date
        FROM ranked
        WHERE rn = 1
        """
    ).fetchall()
    return {normalize_ticker(row[0]): {"price": row[1], "date": row[2]} for row in rows}


def build_reconciliation(expected, actual, prices):
    records = []
    for ticker in sorted(set(expected) | set(actual)):
        exp = expected.get(ticker)
        act = actual.get(ticker)
        exp_shares = exp["shares"] if exp else 0.0
        act_shares = act["shares"] if act else 0.0
        exp_cost = exp["total_cost_basis"] if exp else 0.0
        act_cost = (act.get("total_cost_basis") or 0.0) if act else 0.0
        share_diff = exp_shares - act_shares
        cost_diff = exp_cost - act_cost
        if exp and not act:
            status = "MISSING_FROM_DATABASE"
        elif act and not exp:
            status = "NOT_IN_CURRENT_HOLDINGS"
        elif abs(share_diff) > SHARE_TOLERANCE and abs(cost_diff) > COST_TOLERANCE:
            status = "SHARES_AND_COST_MISMATCH"
        elif abs(share_diff) > SHARE_TOLERANCE:
            status = "SHARE_MISMATCH"
        elif abs(cost_diff) > COST_TOLERANCE:
            status = "COST_MISMATCH"
        else:
            status = "MATCH"
        quote = prices.get(ticker, {})
        price = quote.get("price")
        records.append({
            "ticker": ticker,
            "status": status,
            "expected_shares": exp_shares,
            "database_shares": act_shares,
            "share_difference": share_diff,
            "expected_average_cost": exp["average_cost"] if exp else None,
            "database_average_cost": act.get("average_cost") if act else None,
            "expected_cost_basis": exp_cost,
            "database_cost_basis": act_cost,
            "cost_basis_difference": cost_diff,
            "latest_price": price,
            "calculated_market_value": exp_shares * price if price is not None else None,
            "provided_market_value": exp.get("market_value") if exp else None,
            "price_date": quote.get("date"),
        })
    return records


def write_report(records, output_path):
    fields = list(records[0].keys()) if records else ["ticker", "status"]
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)


def apply_reconciliation(connection, expected, timestamp):
    connection.execute(
        "DELETE FROM portfolio_positions WHERE UPPER(COALESCE(source, '')) = ?",
        (SOURCE,),
    )
    connection.executemany(
        """
        INSERT INTO portfolio_positions
        (ticker, shares, average_cost, total_cost_basis,
         realized_gain_loss, source, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                item["ticker"], item["shares"], item["average_cost"],
                item["total_cost_basis"], 0.0, SOURCE, timestamp,
            )
            for item in expected.values()
        ],
    )
    connection.executemany(
        "INSERT OR IGNORE INTO watchlist (ticker) VALUES (?)",
        [(ticker,) for ticker in expected],
    )
    connection.commit()


def main():
    parser = argparse.ArgumentParser(
        description="Reconcile portfolio_positions to a current Robinhood holdings CSV."
    )
    parser.add_argument("holdings_csv", type=Path, help="Current Robinhood holdings CSV")
    parser.add_argument("--database", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output", type=Path, default=Path("position_reconciliation.csv"))
    parser.add_argument(
        "--apply", action="store_true",
        help="Replace Robinhood portfolio_positions with the current-holdings values."
    )
    args = parser.parse_args()

    if not args.holdings_csv.exists():
        raise FileNotFoundError(f"Holdings CSV not found: {args.holdings_csv}")
    if not args.database.exists():
        raise FileNotFoundError(f"Database not found: {args.database}")

    expected = read_current_holdings(args.holdings_csv)
    if not expected:
        raise ValueError("No positive current holdings were found in the CSV.")

    with sqlite3.connect(args.database) as connection:
        actual = load_database_positions(connection)
        prices = latest_prices(connection)
        records = build_reconciliation(expected, actual, prices)
        if args.apply:
            apply_reconciliation(
                connection, expected, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )

    write_report(records, args.output)
    mismatches = [row for row in records if row["status"] != "MATCH"]
    expected_cost = sum(item["total_cost_basis"] for item in expected.values())
    calculated_value = sum(
        row["calculated_market_value"] or 0.0 for row in records
        if row["ticker"] in expected
    )
    missing_prices = [
        row["ticker"] for row in records
        if row["ticker"] in expected and row["latest_price"] is None
    ]

    print("\n" + "=" * 76)
    print("POSITION AND COST-BASIS RECONCILIATION")
    print("=" * 76)
    print(f"Current holdings in CSV : {len(expected):,}")
    print(f"Database holdings       : {len(actual):,}")
    print(f"Mismatches              : {len(mismatches):,}")
    print(f"Expected cost basis     : ${expected_cost:,.2f}")
    print(f"Calculated market value : ${calculated_value:,.2f}")
    print(f"Missing latest prices   : {len(missing_prices):,}")
    print(f"Report                  : {args.output}")
    print(f"Database updated        : {'YES' if args.apply else 'NO (dry run)'}")
    print("=" * 76)

    for row in mismatches[:30]:
        print(
            f"{row['ticker']:<8} {row['status']:<28} "
            f"shares diff={row['share_difference']:.8f} "
            f"cost diff=${row['cost_basis_difference']:,.2f}"
        )
    if len(mismatches) > 30:
        print("Additional mismatches are in the CSV report.")
    if missing_prices:
        print("Missing prices: " + ", ".join(missing_prices))

    print(
        "\nUse --apply only after reviewing the reconciliation report. "
        "The current-holdings CSV becomes the source of truth for shares and cost basis."
    )


if __name__ == "__main__":
    main()
