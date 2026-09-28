import argparse
import csv
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT / "InvestmentAdvisor.db"
DEFAULT_TEMPLATE_PATH = ROOT / "advisor" / "portfolio_targets_template.csv"
TARGET_TABLE = "portfolio_targets"
GROUP_TABLE = "portfolio_target_groups"

REQUIRED_COLUMNS = {
    "ticker",
    "target_group",
    "min_weight_pct",
    "target_weight_pct",
    "max_weight_pct",
}


def quote_identifier(value):
    return '"' + value.replace('"', '""') + '"'


def table_exists(connection, table_name):
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone() is not None


def table_columns(connection, table_name):
    return {
        row[1]
        for row in connection.execute(
            f"PRAGMA table_info({quote_identifier(table_name)})"
        ).fetchall()
    }


def ensure_tables(connection):
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {GROUP_TABLE} (
            target_group TEXT PRIMARY KEY,
            min_weight_pct REAL NOT NULL,
            target_weight_pct REAL NOT NULL,
            max_weight_pct REAL NOT NULL,
            description TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            updated_timestamp TEXT NOT NULL,
            CHECK (min_weight_pct >= 0),
            CHECK (target_weight_pct >= min_weight_pct),
            CHECK (max_weight_pct >= target_weight_pct),
            CHECK (max_weight_pct <= 100)
        )
        """
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {TARGET_TABLE} (
            ticker TEXT PRIMARY KEY,
            target_group TEXT NOT NULL,
            min_weight_pct REAL NOT NULL,
            target_weight_pct REAL NOT NULL,
            max_weight_pct REAL NOT NULL,
            thesis_status TEXT NOT NULL DEFAULT 'APPROVED',
            allow_buy INTEGER NOT NULL DEFAULT 1,
            allow_sell INTEGER NOT NULL DEFAULT 1,
            notes TEXT,
            source TEXT NOT NULL DEFAULT 'MANUAL',
            updated_timestamp TEXT NOT NULL,
            FOREIGN KEY (target_group) REFERENCES {GROUP_TABLE}(target_group),
            CHECK (min_weight_pct >= 0),
            CHECK (target_weight_pct >= min_weight_pct),
            CHECK (max_weight_pct >= target_weight_pct),
            CHECK (max_weight_pct <= 100),
            CHECK (allow_buy IN (0, 1)),
            CHECK (allow_sell IN (0, 1))
        )
        """
    )
    connection.execute(
        f"CREATE INDEX IF NOT EXISTS idx_portfolio_targets_group "
        f"ON {TARGET_TABLE}(target_group)"
    )


def latest_holdings(connection):
    if not table_exists(connection, "portfolio_dashboard"):
        raise RuntimeError(
            "portfolio_dashboard does not exist. Run "
            "build_portfolio_dashboard_dataset.py first."
        )

    required = {
        "dashboard_date",
        "asset_type",
        "ticker",
        "account_weight_pct",
    }
    missing = required - table_columns(connection, "portfolio_dashboard")
    if missing:
        raise RuntimeError(
            "portfolio_dashboard is missing columns: " + ", ".join(sorted(missing))
        )

    latest_date = connection.execute(
        "SELECT MAX(dashboard_date) FROM portfolio_dashboard"
    ).fetchone()[0]
    if not latest_date:
        raise RuntimeError("portfolio_dashboard is empty.")

    return connection.execute(
        """
        SELECT UPPER(TRIM(ticker)), asset_type, account_weight_pct
        FROM portfolio_dashboard
        WHERE dashboard_date = ?
        ORDER BY account_weight_pct DESC
        """,
        (latest_date,),
    ).fetchall()


def classification_map(connection):
    if not table_exists(connection, "asset_classification"):
        return {}

    required = {"classification_date", "ticker", "asset_class", "asset_subclass"}
    if not required.issubset(table_columns(connection, "asset_classification")):
        return {}

    latest_date = connection.execute(
        "SELECT MAX(classification_date) FROM asset_classification"
    ).fetchone()[0]
    if not latest_date:
        return {}

    return {
        row[0]: (row[1], row[2])
        for row in connection.execute(
            """
            SELECT UPPER(TRIM(ticker)), asset_class, asset_subclass
            FROM asset_classification
            WHERE classification_date = ?
            """,
            (latest_date,),
        ).fetchall()
    }


def suggested_group(ticker, asset_type, asset_class, asset_subclass):
    if ticker == "CASH" or str(asset_type).upper() == "CASH":
        return "CASH"
    asset_class = (asset_class or "").upper()
    asset_subclass = (asset_subclass or "").upper()
    if asset_class == "CRYPTO_ETF":
        return "CRYPTO"
    if asset_class == "LEVERAGED_ETF":
        return "TACTICAL"
    if asset_class == "ETF":
        return "CORE_ETF"
    if asset_class == "EQUITY":
        return "EQUITY"
    return "REVIEW_REQUIRED"


def write_template(connection, output_path):
    holdings = latest_holdings(connection)
    classifications = classification_map(connection)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "ticker",
                "target_group",
                "min_weight_pct",
                "target_weight_pct",
                "max_weight_pct",
                "thesis_status",
                "allow_buy",
                "allow_sell",
                "notes",
            ]
        )
        for ticker, asset_type, current_weight in holdings:
            asset_class, asset_subclass = classifications.get(ticker, (None, None))
            group = suggested_group(ticker, asset_type, asset_class, asset_subclass)
            writer.writerow(
                [
                    ticker,
                    group,
                    "",
                    "",
                    "",
                    "APPROVED",
                    1,
                    1,
                    f"Current account weight: {float(current_weight):.4f}%",
                ]
            )
    return len(holdings)


def parse_boolean(value, field_name, ticker):
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return 1
    if normalized in {"0", "false", "no", "n"}:
        return 0
    raise ValueError(f"{ticker}: {field_name} must be 0/1, true/false, or yes/no.")


def read_targets(csv_path):
    if not csv_path.exists():
        raise FileNotFoundError(f"Target CSV not found: {csv_path}")

    with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(
                "Target CSV is missing columns: " + ", ".join(sorted(missing))
            )

        rows = []
        seen = set()
        for line_number, row in enumerate(reader, start=2):
            ticker = str(row.get("ticker", "")).strip().upper()
            if not ticker:
                continue
            if ticker in seen:
                raise ValueError(f"Duplicate ticker {ticker} on line {line_number}.")
            seen.add(ticker)

            group = str(row.get("target_group", "")).strip().upper()
            if not group:
                raise ValueError(f"{ticker}: target_group is required.")

            try:
                minimum = float(row["min_weight_pct"])
                target = float(row["target_weight_pct"])
                maximum = float(row["max_weight_pct"])
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"{ticker}: min, target, and max weights must be numeric."
                ) from exc

            if not 0 <= minimum <= target <= maximum <= 100:
                raise ValueError(
                    f"{ticker}: weights must satisfy 0 <= min <= target <= max <= 100."
                )

            thesis_status = str(row.get("thesis_status") or "APPROVED").strip().upper()
            allow_buy = parse_boolean(row.get("allow_buy", 1), "allow_buy", ticker)
            allow_sell = parse_boolean(row.get("allow_sell", 1), "allow_sell", ticker)
            notes = str(row.get("notes") or "").strip() or None
            rows.append(
                {
                    "ticker": ticker,
                    "target_group": group,
                    "min_weight_pct": minimum,
                    "target_weight_pct": target,
                    "max_weight_pct": maximum,
                    "thesis_status": thesis_status,
                    "allow_buy": allow_buy,
                    "allow_sell": allow_sell,
                    "notes": notes,
                }
            )

    if not rows:
        raise ValueError("Target CSV contains no usable rows.")
    return rows


def validate_targets(connection, rows):
    current_tickers = {row[0] for row in latest_holdings(connection)}
    target_tickers = {row["ticker"] for row in rows}
    missing = sorted(current_tickers - target_tickers)
    extra = sorted(target_tickers - current_tickers)
    total_target = sum(row["target_weight_pct"] for row in rows)

    if missing:
        raise ValueError("Targets are missing current holdings: " + ", ".join(missing))
    if abs(total_target - 100.0) > 0.01:
        raise ValueError(
            f"Target weights must total 100.00%; current total is {total_target:.4f}%."
        )
    return extra, total_target


def upsert_groups_and_targets(connection, rows, timestamp, replace):
    groups = sorted({row["target_group"] for row in rows})
    group_totals = {
        group: {
            "min": sum(r["min_weight_pct"] for r in rows if r["target_group"] == group),
            "target": sum(r["target_weight_pct"] for r in rows if r["target_group"] == group),
            "max": min(100.0, sum(r["max_weight_pct"] for r in rows if r["target_group"] == group)),
        }
        for group in groups
    }

    if replace:
        connection.execute(f"DELETE FROM {TARGET_TABLE}")
        connection.execute(f"DELETE FROM {GROUP_TABLE}")

    connection.executemany(
        f"""
        INSERT INTO {GROUP_TABLE} (
            target_group, min_weight_pct, target_weight_pct,
            max_weight_pct, description, is_active, updated_timestamp
        ) VALUES (?, ?, ?, ?, ?, 1, ?)
        ON CONFLICT(target_group) DO UPDATE SET
            min_weight_pct=excluded.min_weight_pct,
            target_weight_pct=excluded.target_weight_pct,
            max_weight_pct=excluded.max_weight_pct,
            description=excluded.description,
            is_active=1,
            updated_timestamp=excluded.updated_timestamp
        """,
        [
            (
                group,
                group_totals[group]["min"],
                group_totals[group]["target"],
                group_totals[group]["max"],
                "Calculated from active ticker-level targets",
                timestamp,
            )
            for group in groups
        ],
    )

    connection.executemany(
        f"""
        INSERT INTO {TARGET_TABLE} (
            ticker, target_group, min_weight_pct, target_weight_pct,
            max_weight_pct, thesis_status, allow_buy, allow_sell,
            notes, source, updated_timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'MANUAL_CSV', ?)
        ON CONFLICT(ticker) DO UPDATE SET
            target_group=excluded.target_group,
            min_weight_pct=excluded.min_weight_pct,
            target_weight_pct=excluded.target_weight_pct,
            max_weight_pct=excluded.max_weight_pct,
            thesis_status=excluded.thesis_status,
            allow_buy=excluded.allow_buy,
            allow_sell=excluded.allow_sell,
            notes=excluded.notes,
            source=excluded.source,
            updated_timestamp=excluded.updated_timestamp
        """,
        [
            (
                row["ticker"],
                row["target_group"],
                row["min_weight_pct"],
                row["target_weight_pct"],
                row["max_weight_pct"],
                row["thesis_status"],
                row["allow_buy"],
                row["allow_sell"],
                row["notes"],
                timestamp,
            )
            for row in rows
        ],
    )


def print_summary(connection):
    rows = connection.execute(
        f"""
        SELECT ticker, target_group, min_weight_pct, target_weight_pct,
               max_weight_pct, thesis_status, allow_buy, allow_sell
        FROM {TARGET_TABLE}
        ORDER BY target_weight_pct DESC, ticker
        """
    ).fetchall()

    print("\n" + "=" * 104)
    print("PORTFOLIO TARGETS COMPLETE")
    print("=" * 104)
    print(
        f"{'Ticker':<9}{'Group':<20}{'Min %':>10}{'Target %':>12}"
        f"{'Max %':>10}{'Status':>14}{'Buy':>7}{'Sell':>7}"
    )
    print("-" * 104)
    for ticker, group, minimum, target, maximum, status, buy, sell in rows:
        print(
            f"{ticker:<9}{group:<20}{minimum:>10.2f}{target:>12.2f}"
            f"{maximum:>10.2f}{status:>14}{buy:>7}{sell:>7}"
        )
    print("-" * 104)
    print(f"Total target weight: {sum(row[3] for row in rows):.2f}%")
    print("=" * 104)


def main():
    parser = argparse.ArgumentParser(
        description="Create and maintain policy-based portfolio target weights."
    )
    parser.add_argument("--database", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--targets-csv", type=Path)
    parser.add_argument(
        "--generate-template",
        action="store_true",
        help="Create a CSV template from current holdings without changing the database.",
    )
    parser.add_argument(
        "--template-output", type=Path, default=DEFAULT_TEMPLATE_PATH
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace all existing target and target-group rows with the CSV contents.",
    )
    args = parser.parse_args()

    database_path = args.database.resolve()
    if not database_path.exists():
        raise FileNotFoundError(f"Database not found: {database_path}")

    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        ensure_tables(connection)

        if args.generate_template:
            count = write_template(connection, args.template_output.resolve())
            connection.commit()
            print(f"Created target template with {count} rows: {args.template_output.resolve()}")
            print("Enter min, target, and max weights so target weights total 100%, then import it.")
            return

        if args.targets_csv is None:
            raise ValueError(
                "Provide --targets-csv or use --generate-template. "
                "Target weights are investment-policy inputs and are not guessed by this script."
            )

        rows = read_targets(args.targets_csv.resolve())
        extra, total_target = validate_targets(connection, rows)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        upsert_groups_and_targets(connection, rows, timestamp, args.replace)
        connection.commit()
        print_summary(connection)
        if extra:
            print("Warning: targets not currently held: " + ", ".join(extra))
        print(f"Validated target total: {total_target:.2f}%")


if __name__ == "__main__":
    main()
