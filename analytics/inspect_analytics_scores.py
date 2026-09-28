"""Inspect the analytics_scores table in InvestmentAdvisor.db.

This script is read-only. It reports schema, row counts, date coverage, score
statistics, latest rows, duplicate ticker/date combinations, and overlap with
portfolio holdings and approved research.
"""

import argparse
import sqlite3
from pathlib import Path
from typing import Iterable, Optional

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT / "InvestmentAdvisor.db"
DEFAULT_TABLE = "analytics_scores"

TICKER_CANDIDATES = ("ticker", "symbol")
DATE_CANDIDATES = ("score_date", "as_of_date", "date", "calculation_date", "updated_date")
SCORE_NAME_HINTS = (
    "score", "rank", "percentile", "zscore", "z_score", "rating", "quality",
    "value", "growth", "momentum", "profitability", "risk", "composite",
)
APPROVAL_STATUSES = ("APPROVED", "ACTIVE", "READY", "BUY", "SELECTED")


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone() is not None


def schema_rows(connection: sqlite3.Connection, table_name: str):
    return connection.execute(
        f"PRAGMA table_info({quote_identifier(table_name)})"
    ).fetchall()


def choose_first(columns: Iterable[str], candidates: Iterable[str]) -> Optional[str]:
    available = set(columns)
    return next((name for name in candidates if name in available), None)


def is_numeric_declared_type(type_name: Optional[str]) -> bool:
    normalized = (type_name or "").upper()
    return any(token in normalized for token in ("INT", "REAL", "FLOA", "DOUB", "NUM", "DEC"))


def likely_score_columns(schema):
    results = []
    for _, name, declared_type, *_ in schema:
        lowered = name.lower()
        if is_numeric_declared_type(declared_type) and any(hint in lowered for hint in SCORE_NAME_HINTS):
            results.append(name)
    return results


def print_section(title: str, width: int = 118):
    print("\n" + "=" * width)
    print(title)
    print("=" * width)


def scalar(connection, sql, params=()):
    return connection.execute(sql, params).fetchone()[0]


def inspect_schema(connection, table_name, schema):
    print_section("TABLE SCHEMA")
    print(f"{'CID':>3}  {'Column':<32} {'Declared Type':<18} {'Not Null':>8} {'Default':<22} {'PK':>3}")
    print("-" * 118)
    for cid, name, declared_type, not_null, default_value, primary_key in schema:
        default_text = "" if default_value is None else str(default_value)
        print(
            f"{cid:>3}  {name:<32} {(declared_type or ''):<18} "
            f"{not_null:>8} {default_text:<22} {primary_key:>3}"
        )

    indexes = connection.execute(
        f"PRAGMA index_list({quote_identifier(table_name)})"
    ).fetchall()
    print("\nIndexes:")
    if not indexes:
        print("  None")
    else:
        for index in indexes:
            print("  " + " | ".join(str(value) for value in index))


def inspect_table_summary(connection, table_name, columns, ticker_column, date_column):
    print_section("TABLE SUMMARY")
    table = quote_identifier(table_name)
    row_count = scalar(connection, f"SELECT COUNT(*) FROM {table}")
    print(f"Rows:                    {row_count:,}")
    print(f"Columns:                 {len(columns):,}")
    print(f"Detected ticker column:  {ticker_column or 'NONE'}")
    print(f"Detected date column:    {date_column or 'NONE'}")

    if ticker_column:
        q_ticker = quote_identifier(ticker_column)
        distinct_tickers = scalar(
            connection,
            f"SELECT COUNT(DISTINCT UPPER(TRIM({q_ticker}))) FROM {table} "
            f"WHERE {q_ticker} IS NOT NULL AND TRIM(CAST({q_ticker} AS TEXT)) <> ''",
        )
        blank_tickers = scalar(
            connection,
            f"SELECT COUNT(*) FROM {table} WHERE {q_ticker} IS NULL "
            f"OR TRIM(CAST({q_ticker} AS TEXT)) = ''",
        )
        print(f"Distinct tickers:        {distinct_tickers:,}")
        print(f"Null/blank tickers:      {blank_tickers:,}")

    if date_column:
        q_date = quote_identifier(date_column)
        minimum_date, maximum_date, distinct_dates, null_dates = connection.execute(
            f"SELECT MIN({q_date}), MAX({q_date}), COUNT(DISTINCT {q_date}), "
            f"SUM(CASE WHEN {q_date} IS NULL OR TRIM(CAST({q_date} AS TEXT))='' THEN 1 ELSE 0 END) "
            f"FROM {table}"
        ).fetchone()
        print(f"Minimum date:            {minimum_date}")
        print(f"Maximum date:            {maximum_date}")
        print(f"Distinct dates:          {distinct_dates:,}")
        print(f"Null/blank dates:        {int(null_dates or 0):,}")


def inspect_nulls(connection, table_name, columns):
    print_section("NULL COUNTS BY COLUMN")
    table = quote_identifier(table_name)
    expressions = [
        f"SUM(CASE WHEN {quote_identifier(column)} IS NULL THEN 1 ELSE 0 END)"
        for column in columns
    ]
    values = connection.execute(f"SELECT {', '.join(expressions)} FROM {table}").fetchone()
    total = scalar(connection, f"SELECT COUNT(*) FROM {table}")
    print(f"{'Column':<36} {'Nulls':>12} {'Null %':>12}")
    print("-" * 64)
    for column, value in zip(columns, values):
        nulls = int(value or 0)
        percentage = (100.0 * nulls / total) if total else 0.0
        print(f"{column:<36} {nulls:>12,} {percentage:>11.2f}%")


def inspect_score_columns(connection, table_name, score_columns, date_column):
    print_section("LIKELY SCORE COLUMN STATISTICS")
    if not score_columns:
        print("No numeric columns with score/rank/factor-like names were detected.")
        return

    table = quote_identifier(table_name)
    print(
        f"{'Column':<34} {'Count':>9} {'Nulls':>9} {'Min':>13} {'P25':>13} "
        f"{'Median':>13} {'P75':>13} {'Max':>13} {'Average':>13}"
    )
    print("-" * 142)

    for column in score_columns:
        q_column = quote_identifier(column)
        values = [
            float(row[0])
            for row in connection.execute(
                f"SELECT CAST({q_column} AS REAL) FROM {table} "
                f"WHERE {q_column} IS NOT NULL ORDER BY CAST({q_column} AS REAL)"
            ).fetchall()
        ]
        total = scalar(connection, f"SELECT COUNT(*) FROM {table}")
        if not values:
            print(f"{column:<34} {0:>9} {total:>9} {'N/A':>13}")
            continue

        def percentile(p):
            if len(values) == 1:
                return values[0]
            position = (len(values) - 1) * p
            lower = int(math.floor(position))
            upper = int(math.ceil(position))
            if lower == upper:
                return values[lower]
            return values[lower] + (values[upper] - values[lower]) * (position - lower)

        average = sum(values) / len(values)
        print(
            f"{column:<34} {len(values):>9,} {total-len(values):>9,} "
            f"{min(values):>13.4f} {percentile(.25):>13.4f} {percentile(.50):>13.4f} "
            f"{percentile(.75):>13.4f} {max(values):>13.4f} {average:>13.4f}"
        )

        negative = sum(value < 0 for value in values)
        zero = sum(value == 0 for value in values)
        above_100 = sum(value > 100 for value in values)
        print(
            f"  Distribution flags: negative={negative:,}, zero={zero:,}, "
            f">100={above_100:,}"
        )

    if date_column:
        latest_date = scalar(
            connection,
            f"SELECT MAX({quote_identifier(date_column)}) FROM {table}",
        )
        print(f"\nLatest score date used for downstream review: {latest_date}")


def inspect_duplicates(connection, table_name, ticker_column, date_column):
    print_section("DUPLICATE CHECK")
    if not ticker_column:
        print("Cannot inspect duplicate ticker keys because no ticker column was detected.")
        return
    table = quote_identifier(table_name)
    ticker = quote_identifier(ticker_column)
    if date_column:
        date = quote_identifier(date_column)
        rows = connection.execute(
            f"SELECT UPPER(TRIM({ticker})), {date}, COUNT(*) AS row_count "
            f"FROM {table} GROUP BY UPPER(TRIM({ticker})), {date} "
            f"HAVING COUNT(*) > 1 ORDER BY row_count DESC LIMIT 25"
        ).fetchall()
        label = "ticker/date"
    else:
        rows = connection.execute(
            f"SELECT UPPER(TRIM({ticker})), COUNT(*) AS row_count "
            f"FROM {table} GROUP BY UPPER(TRIM({ticker})) "
            f"HAVING COUNT(*) > 1 ORDER BY row_count DESC LIMIT 25"
        ).fetchall()
        label = "ticker"
    if not rows:
        print(f"No duplicate {label} keys found.")
    else:
        print(f"Top duplicate {label} keys:")
        for row in rows:
            print("  " + " | ".join(str(value) for value in row))


def inspect_latest_rows(connection, table_name, columns, ticker_column, date_column, limit):
    print_section(f"LATEST/SAMPLE ROWS (LIMIT {limit})")
    table = quote_identifier(table_name)
    ordering = []
    if date_column:
        ordering.append(f"{quote_identifier(date_column)} DESC")
    if ticker_column:
        ordering.append(f"UPPER(TRIM({quote_identifier(ticker_column)}))")
    order_sql = " ORDER BY " + ", ".join(ordering) if ordering else ""
    rows = connection.execute(f"SELECT * FROM {table}{order_sql} LIMIT ?", (limit,)).fetchall()
    print(" | ".join(columns))
    print("-" * 118)
    for row in rows:
        print(" | ".join("NULL" if value is None else str(value) for value in row))
    if not rows:
        print("No rows found.")


def inspect_key_tickers(connection, table_name, columns, ticker_column, date_column, score_columns, tickers):
    print_section("KEY TICKER SCORE REVIEW")
    if not ticker_column:
        print("No ticker column detected.")
        return
    selected = [ticker.strip().upper() for ticker in tickers.split(",") if ticker.strip()]
    if not selected:
        print("No key tickers requested.")
        return
    display_columns = [ticker_column]
    if date_column:
        display_columns.append(date_column)
    display_columns.extend(score_columns)
    display_columns = list(dict.fromkeys(display_columns))
    select_sql = ", ".join(quote_identifier(column) for column in display_columns)
    placeholders = ",".join("?" for _ in selected)
    order_sql = f", {quote_identifier(date_column)} DESC" if date_column else ""
    rows = connection.execute(
        f"SELECT {select_sql} FROM {quote_identifier(table_name)} "
        f"WHERE UPPER(TRIM({quote_identifier(ticker_column)})) IN ({placeholders}) "
        f"ORDER BY UPPER(TRIM({quote_identifier(ticker_column)})){order_sql}",
        selected,
    ).fetchall()
    print(" | ".join(display_columns))
    print("-" * 118)
    for row in rows:
        print(" | ".join("NULL" if value is None else str(value) for value in row))
    missing = sorted(set(selected) - {str(row[0]).upper() for row in rows})
    if missing:
        print("\nNot present in analytics_scores: " + ", ".join(missing))


def inspect_overlap(connection, table_name, ticker_column):
    print_section("DOWNSTREAM OVERLAP")
    if not ticker_column:
        print("No ticker column detected.")
        return
    source = quote_identifier(table_name)
    ticker = quote_identifier(ticker_column)

    if table_exists(connection, "portfolio_dashboard"):
        dashboard_columns = {row[1] for row in schema_rows(connection, "portfolio_dashboard")}
        if {"dashboard_date", "ticker", "asset_type"}.issubset(dashboard_columns):
            latest = scalar(connection, "SELECT MAX(dashboard_date) FROM portfolio_dashboard")
            total, matched = connection.execute(
                f"SELECT COUNT(DISTINCT UPPER(TRIM(d.ticker))), "
                f"COUNT(DISTINCT CASE WHEN a.score_ticker IS NOT NULL THEN UPPER(TRIM(d.ticker)) END) "
                f"FROM portfolio_dashboard d LEFT JOIN "
                f"(SELECT DISTINCT UPPER(TRIM({ticker})) AS score_ticker FROM {source}) a "
                f"ON a.score_ticker=UPPER(TRIM(d.ticker)) "
                f"WHERE d.dashboard_date=? AND d.asset_type='SECURITY'",
                (latest,),
            ).fetchone()
            print(f"Current portfolio holdings matched: {matched:,} of {total:,}")

    if table_exists(connection, "research_queue"):
        rq_columns = {row[1] for row in schema_rows(connection, "research_queue")}
        rq_ticker = choose_first(rq_columns, TICKER_CANDIDATES)
        rq_status = choose_first(rq_columns, ("status", "research_status", "approval_status"))
        if rq_ticker and rq_status:
            placeholders = ",".join("?" for _ in APPROVAL_STATUSES)
            total, matched = connection.execute(
                f"SELECT COUNT(DISTINCT UPPER(TRIM(r.{quote_identifier(rq_ticker)}))), "
                f"COUNT(DISTINCT CASE WHEN a.score_ticker IS NOT NULL "
                f"THEN UPPER(TRIM(r.{quote_identifier(rq_ticker)})) END) "
                f"FROM research_queue r LEFT JOIN "
                f"(SELECT DISTINCT UPPER(TRIM({ticker})) AS score_ticker FROM {source}) a "
                f"ON a.score_ticker=UPPER(TRIM(r.{quote_identifier(rq_ticker)})) "
                f"WHERE UPPER(TRIM(r.{quote_identifier(rq_status)})) IN ({placeholders})",
                APPROVAL_STATUSES,
            ).fetchone()
            print(f"Approved research ideas matched:  {matched:,} of {total:,}")


def print_interpretation(score_columns):
    print_section("INTERPRETATION GUIDE")
    if not score_columns:
        print("No likely score fields were detected; inspect the schema and sample rows above.")
        return
    print("Review the statistics above before selecting an advisor input column:")
    print("  * A 0-100 composite/percentile score can usually be consumed directly.")
    print("  * A negative-to-positive factor or alpha score must be normalized before use.")
    print("  * A rank where 1 is best must be inverted or converted to a percentile.")
    print("  * A return/alpha percentage should not be treated as a 0-100 quality score.")
    print("  * Confirm that the latest date has one row per ticker before modeling.")
    print("Detected likely score columns: " + ", ".join(score_columns))


def main():
    parser = argparse.ArgumentParser(description="Inspect analytics_scores structure and distributions.")
    parser.add_argument("--database", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--table", default=DEFAULT_TABLE)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument(
        "--tickers",
        default="MSFT,PLTR,NOW,ORCL,SNDK,ICHR,HIMS,BX,VOO,QQQ,DRAM",
        help="Comma-separated ticker list for focused review.",
    )
    args = parser.parse_args()

    database_path = args.database.resolve()
    if not database_path.exists():
        raise FileNotFoundError(f"Database not found: {database_path}")
    if args.limit < 1:
        raise ValueError("--limit must be at least 1.")

    with sqlite3.connect(database_path) as connection:
        if not table_exists(connection, args.table):
            available = [
                row[0] for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                ).fetchall()
            ]
            raise RuntimeError(
                f"Table {args.table!r} does not exist. Available tables: {', '.join(available)}"
            )

        schema = schema_rows(connection, args.table)
        column_names = [row[1] for row in schema]
        ticker_column = choose_first(column_names, TICKER_CANDIDATES)
        date_column = choose_first(column_names, DATE_CANDIDATES)
        score_columns = likely_score_columns(schema)

        print_section("ANALYTICS SCORES INSPECTION")
        print(f"Database: {database_path}")
        print(f"Table:    {args.table}")
        print("Mode:     READ ONLY")

        inspect_schema(connection, args.table, schema)
        inspect_table_summary(
            connection, args.table, column_names, ticker_column, date_column
        )
        inspect_nulls(connection, args.table, column_names)
        inspect_score_columns(connection, args.table, score_columns, date_column)
        inspect_duplicates(connection, args.table, ticker_column, date_column)
        inspect_latest_rows(
            connection, args.table, column_names, ticker_column, date_column, args.limit
        )
        inspect_key_tickers(
            connection, args.table, column_names, ticker_column, date_column,
            score_columns, args.tickers
        )
        inspect_overlap(connection, args.table, ticker_column)
        print_interpretation(score_columns)


if __name__ == "__main__":
    import math
    main()
