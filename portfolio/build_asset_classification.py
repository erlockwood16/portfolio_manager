import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT / "InvestmentAdvisor.db"
DEFAULT_DASHBOARD_TABLE = "portfolio_dashboard"
DEFAULT_UNIVERSE_TABLE = "company_universe"
OUTPUT_TABLE = "asset_classification"
OVERRIDE_TABLE = "asset_classification_overrides"

# Seed rules for known fund holdings. User-maintained overrides in SQLite take precedence.
DEFAULT_OVERRIDES = [
    ("QQQ", "ETF", "NASDAQ-100 ETF", "SYSTEM_SEED"),
    ("VOO", "ETF", "S&P 500 ETF", "SYSTEM_SEED"),
    ("VLUE", "ETF", "Factor ETF", "SYSTEM_SEED"),
    ("IBIT", "CRYPTO_ETF", "Spot Bitcoin ETF", "SYSTEM_SEED"),
    ("DRAM", "ETF", "Thematic ETF", "SYSTEM_SEED"),
    ("DRAL", "LEVERAGED_ETF", "Leveraged single-stock ETF", "SYSTEM_SEED"),
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
        row[1]
        for row in connection.execute(
            f"PRAGMA table_info({quote_identifier(table_name)})"
        ).fetchall()
    }


def ensure_tables(connection):
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {OVERRIDE_TABLE} (
            ticker TEXT PRIMARY KEY,
            asset_class TEXT NOT NULL,
            asset_subclass TEXT,
            classification_source TEXT NOT NULL,
            notes TEXT,
            updated_timestamp TEXT NOT NULL
        )
        """
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {OUTPUT_TABLE} (
            classification_date TEXT NOT NULL,
            ticker TEXT NOT NULL,
            asset_class TEXT NOT NULL,
            asset_subclass TEXT,
            sector TEXT,
            industry TEXT,
            universe_source TEXT,
            classification_source TEXT NOT NULL,
            market_value REAL NOT NULL,
            account_weight_pct REAL NOT NULL,
            is_classified INTEGER NOT NULL,
            updated_timestamp TEXT NOT NULL,
            PRIMARY KEY (classification_date, ticker)
        )
        """
    )
    connection.execute(
        f"CREATE INDEX IF NOT EXISTS idx_asset_classification_date "
        f"ON {OUTPUT_TABLE}(classification_date DESC)"
    )
    connection.execute(
        f"CREATE INDEX IF NOT EXISTS idx_asset_classification_class "
        f"ON {OUTPUT_TABLE}(asset_class, classification_date DESC)"
    )


def seed_default_overrides(connection, timestamp):
    connection.executemany(
        f"""
        INSERT INTO {OVERRIDE_TABLE} (
            ticker, asset_class, asset_subclass,
            classification_source, notes, updated_timestamp
        ) VALUES (?, ?, ?, ?, NULL, ?)
        ON CONFLICT(ticker) DO NOTHING
        """,
        [(*row, timestamp) for row in DEFAULT_OVERRIDES],
    )


def validate_sources(connection, dashboard_table, universe_table):
    if not table_exists(connection, dashboard_table):
        raise RuntimeError(
            f"{dashboard_table} does not exist. Run build_portfolio_dashboard_dataset.py first."
        )
    required_dashboard = {
        "dashboard_date", "asset_type", "ticker", "market_value", "account_weight_pct"
    }
    missing = required_dashboard - table_columns(connection, dashboard_table)
    if missing:
        raise RuntimeError(
            f"{dashboard_table} is missing columns: {', '.join(sorted(missing))}"
        )
    if not table_exists(connection, universe_table):
        raise RuntimeError(f"{universe_table} does not exist.")
    if "ticker" not in table_columns(connection, universe_table):
        raise RuntimeError(f"{universe_table} must contain ticker.")


def load_holdings(connection, dashboard_table, classification_date=None):
    if classification_date is None:
        classification_date = connection.execute(
            f"SELECT MAX(dashboard_date) FROM {quote_identifier(dashboard_table)}"
        ).fetchone()[0]
    if not classification_date:
        raise RuntimeError(f"{dashboard_table} is empty.")

    holdings = pd.read_sql_query(
        f"""
        SELECT dashboard_date AS classification_date,
               UPPER(TRIM(ticker)) AS ticker,
               asset_type,
               market_value,
               account_weight_pct
        FROM {quote_identifier(dashboard_table)}
        WHERE dashboard_date = ?
        ORDER BY account_weight_pct DESC
        """,
        connection,
        params=(classification_date,),
    )
    if holdings.empty:
        raise RuntimeError(f"No dashboard rows found for {classification_date}.")
    return classification_date, holdings


def load_universe(connection, universe_table):
    available = table_columns(connection, universe_table)
    select_parts = ["UPPER(TRIM(ticker)) AS ticker"]
    for column in ("sector", "industry", "source"):
        select_parts.append(column if column in available else f"NULL AS {column}")

    universe = pd.read_sql_query(
        f"SELECT {', '.join(select_parts)} FROM {quote_identifier(universe_table)}",
        connection,
    )
    if universe.empty:
        return universe
    # A ticker can occur in multiple index sources; retain one classification row.
    universe = universe.sort_values("ticker").drop_duplicates("ticker", keep="first")
    return universe.rename(columns={"source": "universe_source"})


def load_overrides(connection):
    return pd.read_sql_query(
        f"""
        SELECT UPPER(TRIM(ticker)) AS ticker,
               asset_class AS override_asset_class,
               asset_subclass AS override_asset_subclass,
               classification_source AS override_source
        FROM {OVERRIDE_TABLE}
        """,
        connection,
    )


def classify_assets(holdings, universe, overrides):
    results = holdings.merge(universe, on="ticker", how="left")
    results = results.merge(overrides, on="ticker", how="left")

    is_cash = results["asset_type"].str.upper().eq("CASH") | results["ticker"].eq("CASH")
    has_override = results["override_asset_class"].notna()
    in_universe = results["universe_source"].notna()

    results["asset_class"] = "UNCLASSIFIED"
    results["asset_subclass"] = None
    results["classification_source"] = "UNCLASSIFIED"

    results.loc[in_universe, "asset_class"] = "EQUITY"
    results.loc[in_universe, "asset_subclass"] = "PUBLIC_EQUITY"
    results.loc[in_universe, "classification_source"] = "COMPANY_UNIVERSE"

    results.loc[has_override, "asset_class"] = results.loc[
        has_override, "override_asset_class"
    ]
    results.loc[has_override, "asset_subclass"] = results.loc[
        has_override, "override_asset_subclass"
    ]
    results.loc[has_override, "classification_source"] = results.loc[
        has_override, "override_source"
    ]

    results.loc[is_cash, "asset_class"] = "CASH"
    results.loc[is_cash, "asset_subclass"] = "BROKERAGE_CASH"
    results.loc[is_cash, "classification_source"] = "PORTFOLIO_DASHBOARD"
    results.loc[is_cash, ["sector", "industry", "universe_source"]] = None

    results["is_classified"] = results["asset_class"].ne("UNCLASSIFIED").astype(int)
    return results


def upsert_results(connection, results, timestamp, full_refresh=False):
    classification_date = results["classification_date"].iloc[0]
    if full_refresh:
        connection.execute(
            f"DELETE FROM {OUTPUT_TABLE} WHERE classification_date = ?",
            (classification_date,),
        )

    rows = []
    for row in results.itertuples(index=False):
        rows.append(
            (
                row.classification_date,
                row.ticker,
                row.asset_class,
                None if pd.isna(row.asset_subclass) else row.asset_subclass,
                None if pd.isna(row.sector) else row.sector,
                None if pd.isna(row.industry) else row.industry,
                None if pd.isna(row.universe_source) else row.universe_source,
                row.classification_source,
                float(row.market_value),
                float(row.account_weight_pct),
                int(row.is_classified),
                timestamp,
            )
        )

    connection.executemany(
        f"""
        INSERT INTO {OUTPUT_TABLE} (
            classification_date, ticker, asset_class, asset_subclass,
            sector, industry, universe_source, classification_source,
            market_value, account_weight_pct, is_classified, updated_timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(classification_date, ticker) DO UPDATE SET
            asset_class=excluded.asset_class,
            asset_subclass=excluded.asset_subclass,
            sector=excluded.sector,
            industry=excluded.industry,
            universe_source=excluded.universe_source,
            classification_source=excluded.classification_source,
            market_value=excluded.market_value,
            account_weight_pct=excluded.account_weight_pct,
            is_classified=excluded.is_classified,
            updated_timestamp=excluded.updated_timestamp
        """,
        rows,
    )
    return len(rows)


def print_summary(results, database_path):
    allocation = (
        results.groupby("asset_class", as_index=False)
        .agg(
            holding_count=("ticker", "nunique"),
            market_value=("market_value", "sum"),
            account_weight_pct=("account_weight_pct", "sum"),
        )
        .sort_values("account_weight_pct", ascending=False)
    )
    unclassified = results.loc[results["is_classified"].eq(0), "ticker"].tolist()

    print("\n" + "=" * 92)
    print("ASSET CLASSIFICATION COMPLETE")
    print("=" * 92)
    print(f"Database:             {database_path}")
    print(f"Classification date:  {results['classification_date'].iloc[0]}")
    print(f"Assets processed:     {len(results):,}")
    print(f"Assets classified:    {int(results['is_classified'].sum()):,}")
    print(f"Assets unclassified:  {len(unclassified):,}")
    print("\nASSET ALLOCATION")
    print(
        allocation.to_string(
            index=False,
            float_format=lambda value: f"{value:,.2f}",
        )
    )
    if unclassified:
        print("\nUNCLASSIFIED TICKERS")
        print(", ".join(unclassified))
        print(
            f"Add or update these in {OVERRIDE_TABLE}, then rerun with --full-refresh."
        )
    print("=" * 92)


def main():
    parser = argparse.ArgumentParser(
        description="Classify portfolio holdings by asset class and subtype."
    )
    parser.add_argument("--database", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--dashboard-table", default=DEFAULT_DASHBOARD_TABLE)
    parser.add_argument("--universe-table", default=DEFAULT_UNIVERSE_TABLE)
    parser.add_argument("--classification-date")
    parser.add_argument("--full-refresh", action="store_true")
    args = parser.parse_args()

    database_path = args.database.resolve()
    if not database_path.exists():
        raise FileNotFoundError(f"Database not found: {database_path}")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(database_path) as connection:
        validate_sources(connection, args.dashboard_table, args.universe_table)
        ensure_tables(connection)
        seed_default_overrides(connection, timestamp)
        classification_date, holdings = load_holdings(
            connection, args.dashboard_table, args.classification_date
        )
        universe = load_universe(connection, args.universe_table)
        overrides = load_overrides(connection)
        results = classify_assets(holdings, universe, overrides)
        rows_written = upsert_results(
            connection, results, timestamp, args.full_refresh
        )
        connection.commit()

    if rows_written != len(results):
        raise RuntimeError("Not all asset classification rows were written.")
    print_summary(results, database_path)


if __name__ == "__main__":
    main()
