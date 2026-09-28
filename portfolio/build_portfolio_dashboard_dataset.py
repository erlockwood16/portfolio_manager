import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT / "InvestmentAdvisor.db"
DEFAULT_POSITIONS_TABLE = "portfolio_positions"
DEFAULT_PRICES_TABLE = "prices"
DEFAULT_CASH_TABLE = "portfolio_cash"
OUTPUT_TABLE = "portfolio_dashboard"


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


def choose_column(columns, candidates, label, required=True):
    for candidate in candidates:
        if candidate in columns:
            return candidate
    if required:
        raise RuntimeError(
            f"Could not identify {label}. Expected one of: {', '.join(candidates)}"
        )
    return None


def validate_source_tables(connection, positions_table, prices_table, cash_table):
    for table_name in (positions_table, prices_table, cash_table):
        if not table_exists(connection, table_name):
            raise RuntimeError(f"Required table '{table_name}' does not exist.")


def detect_schema(connection, positions_table, prices_table, cash_table):
    position_columns = table_columns(connection, positions_table)
    price_columns = table_columns(connection, prices_table)
    cash_columns = table_columns(connection, cash_table)

    return {
        "position_ticker": choose_column(
            position_columns, ["ticker", "symbol"], "position ticker"
        ),
        "shares": choose_column(
            position_columns,
            ["shares", "quantity", "current_quantity", "share_quantity"],
            "position shares",
        ),
        "total_cost_basis": choose_column(
            position_columns,
            ["total_cost_basis", "cost_basis", "position_cost_basis"],
            "total cost basis",
            required=False,
        ),
        "average_cost": choose_column(
            position_columns,
            ["average_cost", "avg_cost", "average_price", "avg_price"],
            "average cost",
            required=False,
        ),
        "source": choose_column(
            position_columns, ["source", "broker"], "position source", required=False
        ),
        "price_ticker": choose_column(
            price_columns, ["ticker", "symbol"], "price ticker"
        ),
        "price_date": choose_column(
            price_columns, ["price_date", "date", "trade_date"], "price date"
        ),
        "close_price": choose_column(
            price_columns,
            ["adjusted_close", "adj_close", "close_price", "close"],
            "closing price",
        ),
        "cash_balance": choose_column(
            cash_columns, ["cash_balance", "balance", "amount"], "cash balance"
        ),
        "cash_source": choose_column(
            cash_columns, ["source", "broker", "account_name"], "cash source", required=False
        ),
        "cash_updated": choose_column(
            cash_columns,
            ["last_updated", "updated_timestamp", "created_timestamp"],
            "cash update timestamp",
            required=False,
        ),
    }


def ensure_output_table(connection):
    required_columns = {
        "dashboard_date", "asset_type", "ticker", "shares", "current_price",
        "price_date", "market_value", "cost_basis", "unrealized_pnl",
        "unrealized_return_pct", "daily_pnl", "contribution_pct",
        "account_weight_pct", "invested_weight_pct", "source",
        "total_invested_value", "cash_balance", "cash_weight_pct",
        "total_account_value", "updated_timestamp",
    }

    if table_exists(connection, OUTPUT_TABLE):
        existing = table_columns(connection, OUTPUT_TABLE)
        if not required_columns.issubset(existing):
            backup_name = (
                f"{OUTPUT_TABLE}_legacy_" + datetime.now().strftime("%Y%m%d_%H%M%S")
            )
            connection.execute(
                f"ALTER TABLE {quote_identifier(OUTPUT_TABLE)} "
                f"RENAME TO {quote_identifier(backup_name)}"
            )
            print(f"Backed up incompatible {OUTPUT_TABLE} table as {backup_name}.")

    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {OUTPUT_TABLE} (
            dashboard_date TEXT NOT NULL,
            asset_type TEXT NOT NULL,
            ticker TEXT NOT NULL,
            shares REAL,
            current_price REAL,
            price_date TEXT,
            market_value REAL NOT NULL,
            cost_basis REAL,
            unrealized_pnl REAL,
            unrealized_return_pct REAL,
            daily_pnl REAL,
            contribution_pct REAL,
            account_weight_pct REAL NOT NULL,
            invested_weight_pct REAL,
            source TEXT,
            total_invested_value REAL NOT NULL,
            cash_balance REAL NOT NULL,
            cash_weight_pct REAL NOT NULL,
            total_account_value REAL NOT NULL,
            updated_timestamp TEXT NOT NULL,
            PRIMARY KEY (dashboard_date, asset_type, ticker)
        )
        """
    )
    connection.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_portfolio_dashboard_date
        ON {OUTPUT_TABLE} (dashboard_date DESC)
        """
    )
    connection.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_portfolio_dashboard_ticker_date
        ON {OUTPUT_TABLE} (ticker, dashboard_date DESC)
        """
    )


def load_positions(connection, positions_table, schema):
    ticker = quote_identifier(schema["position_ticker"])
    shares = quote_identifier(schema["shares"])

    if schema["total_cost_basis"]:
        cost_expression = (
            f"SUM(COALESCE({quote_identifier(schema['total_cost_basis'])}, 0))"
        )
    elif schema["average_cost"]:
        average_cost = quote_identifier(schema["average_cost"])
        cost_expression = (
            f"SUM(COALESCE({shares}, 0) * COALESCE({average_cost}, 0))"
        )
    else:
        raise RuntimeError(
            "The positions table must contain total cost basis or average cost."
        )

    source_expression = (
        f"MAX({quote_identifier(schema['source'])})"
        if schema["source"]
        else "NULL"
    )

    query = f"""
        SELECT
            UPPER(TRIM({ticker})) AS ticker,
            SUM(COALESCE({shares}, 0)) AS shares,
            {cost_expression} AS cost_basis,
            {source_expression} AS source
        FROM {quote_identifier(positions_table)}
        WHERE {ticker} IS NOT NULL
        GROUP BY UPPER(TRIM({ticker}))
        HAVING ABS(SUM(COALESCE({shares}, 0))) > 0.00000001
        ORDER BY ticker
    """
    positions = pd.read_sql_query(query, connection)
    if positions.empty:
        raise RuntimeError(f"No open positions were found in {positions_table}.")
    return positions


def load_cash(connection, cash_table, schema):
    cash_balance = quote_identifier(schema["cash_balance"])
    order_clause = (
        f"ORDER BY {quote_identifier(schema['cash_updated'])} DESC"
        if schema["cash_updated"]
        else "ORDER BY rowid DESC"
    )
    source_expression = (
        quote_identifier(schema["cash_source"])
        if schema["cash_source"]
        else "NULL"
    )

    row = connection.execute(
        f"""
        SELECT {cash_balance}, {source_expression}
        FROM {quote_identifier(cash_table)}
        WHERE {cash_balance} IS NOT NULL
        {order_clause}
        LIMIT 1
        """
    ).fetchone()
    if row is None:
        raise RuntimeError(f"No cash balance was found in {cash_table}.")
    return float(row[0]), row[1]


def load_latest_prices(connection, prices_table, schema, tickers, as_of_date=None):
    placeholders = ",".join("?" for _ in tickers)
    ticker = quote_identifier(schema["price_ticker"])
    price_date = quote_identifier(schema["price_date"])
    close_price = quote_identifier(schema["close_price"])

    parameters = list(tickers)
    date_filter = ""
    if as_of_date:
        date_filter = f"AND date({price_date}) <= date(?)"
        parameters.append(as_of_date)

    query = f"""
        SELECT
            UPPER(TRIM({ticker})) AS ticker,
            date({price_date}) AS price_date,
            {close_price} AS close_price
        FROM {quote_identifier(prices_table)}
        WHERE UPPER(TRIM({ticker})) IN ({placeholders})
          AND {close_price} IS NOT NULL
          {date_filter}
        ORDER BY ticker, date({price_date})
    """
    prices = pd.read_sql_query(query, connection, params=parameters)
    if prices.empty:
        raise RuntimeError("No prices were found for the open positions.")

    prices["price_date"] = pd.to_datetime(prices["price_date"], errors="coerce")
    prices["close_price"] = pd.to_numeric(prices["close_price"], errors="coerce")
    prices = prices.dropna(subset=["ticker", "price_date", "close_price"])
    prices = prices[prices["close_price"] > 0]
    prices = prices.drop_duplicates(["ticker", "price_date"], keep="last")

    latest = prices.groupby("ticker", as_index=False).tail(1).copy()
    prior = prices.groupby("ticker", as_index=False).nth(-2).reset_index()
    latest = latest.rename(columns={"close_price": "current_price"})
    prior = prior[["ticker", "close_price"]].rename(
        columns={"close_price": "prior_price"}
    )
    return latest.merge(prior, on="ticker", how="left")


def build_dashboard(positions, prices, cash_balance, cash_source, as_of_date=None):
    holdings = positions.merge(prices, on="ticker", how="left")
    missing = holdings.loc[holdings["current_price"].isna(), "ticker"].tolist()
    if missing:
        raise RuntimeError(
            "Missing current prices for open positions: " + ", ".join(missing)
        )

    holdings["market_value"] = holdings["shares"] * holdings["current_price"]
    holdings["unrealized_pnl"] = holdings["market_value"] - holdings["cost_basis"]
    holdings["unrealized_return_pct"] = holdings["unrealized_pnl"].div(
        holdings["cost_basis"].replace(0, pd.NA)
    ) * 100.0
    holdings["daily_pnl"] = holdings["shares"] * (
        holdings["current_price"] - holdings["prior_price"]
    )

    total_invested_value = float(holdings["market_value"].sum())
    total_account_value = total_invested_value + cash_balance
    if total_account_value == 0:
        raise RuntimeError("Total account value is zero.")

    previous_invested_value = float(
        (holdings["shares"] * holdings["prior_price"]).sum(min_count=1)
    )
    holdings["contribution_pct"] = (
        holdings["daily_pnl"] / previous_invested_value * 100.0
        if previous_invested_value
        else pd.NA
    )
    holdings["account_weight_pct"] = (
        holdings["market_value"] / total_account_value * 100.0
    )
    holdings["invested_weight_pct"] = (
        holdings["market_value"] / total_invested_value * 100.0
        if total_invested_value
        else pd.NA
    )
    holdings["asset_type"] = "SECURITY"
    holdings["cash_balance"] = cash_balance
    holdings["cash_weight_pct"] = cash_balance / total_account_value * 100.0
    holdings["total_invested_value"] = total_invested_value
    holdings["total_account_value"] = total_account_value

    dashboard_date = (
        as_of_date
        if as_of_date
        else holdings["price_date"].max().strftime("%Y-%m-%d")
    )
    holdings["dashboard_date"] = dashboard_date
    holdings["price_date"] = holdings["price_date"].dt.strftime("%Y-%m-%d")

    cash_row = pd.DataFrame(
        [{
            "dashboard_date": dashboard_date,
            "asset_type": "CASH",
            "ticker": "CASH",
            "shares": None,
            "current_price": None,
            "price_date": dashboard_date,
            "market_value": cash_balance,
            "cost_basis": cash_balance,
            "unrealized_pnl": 0.0,
            "unrealized_return_pct": 0.0,
            "daily_pnl": 0.0,
            "contribution_pct": 0.0,
            "account_weight_pct": cash_balance / total_account_value * 100.0,
            "invested_weight_pct": None,
            "source": cash_source or "ROBINHOOD",
            "total_invested_value": total_invested_value,
            "cash_balance": cash_balance,
            "cash_weight_pct": cash_balance / total_account_value * 100.0,
            "total_account_value": total_account_value,
        }]
    )

    columns = [
        "dashboard_date", "asset_type", "ticker", "shares", "current_price",
        "price_date", "market_value", "cost_basis", "unrealized_pnl",
        "unrealized_return_pct", "daily_pnl", "contribution_pct",
        "account_weight_pct", "invested_weight_pct", "source",
        "total_invested_value", "cash_balance", "cash_weight_pct",
        "total_account_value",
    ]
    dashboard = pd.concat([holdings[columns], cash_row[columns]], ignore_index=True)
    return dashboard.sort_values(
        ["asset_type", "account_weight_pct"], ascending=[True, False]
    ).reset_index(drop=True)


def upsert_dashboard(connection, dashboard, timestamp, full_refresh=False):
    dashboard_date = dashboard["dashboard_date"].iloc[0]
    if full_refresh:
        connection.execute(
            f"DELETE FROM {OUTPUT_TABLE} WHERE dashboard_date = ?",
            (dashboard_date,),
        )

    rows = []
    for row in dashboard.itertuples(index=False):
        rows.append((
            row.dashboard_date,
            row.asset_type,
            row.ticker,
            None if pd.isna(row.shares) else float(row.shares),
            None if pd.isna(row.current_price) else float(row.current_price),
            row.price_date,
            float(row.market_value),
            None if pd.isna(row.cost_basis) else float(row.cost_basis),
            None if pd.isna(row.unrealized_pnl) else float(row.unrealized_pnl),
            None if pd.isna(row.unrealized_return_pct) else float(row.unrealized_return_pct),
            None if pd.isna(row.daily_pnl) else float(row.daily_pnl),
            None if pd.isna(row.contribution_pct) else float(row.contribution_pct),
            float(row.account_weight_pct),
            None if pd.isna(row.invested_weight_pct) else float(row.invested_weight_pct),
            row.source,
            float(row.total_invested_value),
            float(row.cash_balance),
            float(row.cash_weight_pct),
            float(row.total_account_value),
            timestamp,
        ))

    connection.executemany(
        f"""
        INSERT INTO {OUTPUT_TABLE} (
            dashboard_date, asset_type, ticker, shares, current_price,
            price_date, market_value, cost_basis, unrealized_pnl,
            unrealized_return_pct, daily_pnl, contribution_pct,
            account_weight_pct, invested_weight_pct, source,
            total_invested_value, cash_balance, cash_weight_pct,
            total_account_value, updated_timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(dashboard_date, asset_type, ticker) DO UPDATE SET
            shares=excluded.shares,
            current_price=excluded.current_price,
            price_date=excluded.price_date,
            market_value=excluded.market_value,
            cost_basis=excluded.cost_basis,
            unrealized_pnl=excluded.unrealized_pnl,
            unrealized_return_pct=excluded.unrealized_return_pct,
            daily_pnl=excluded.daily_pnl,
            contribution_pct=excluded.contribution_pct,
            account_weight_pct=excluded.account_weight_pct,
            invested_weight_pct=excluded.invested_weight_pct,
            source=excluded.source,
            total_invested_value=excluded.total_invested_value,
            cash_balance=excluded.cash_balance,
            cash_weight_pct=excluded.cash_weight_pct,
            total_account_value=excluded.total_account_value,
            updated_timestamp=excluded.updated_timestamp
        """,
        rows,
    )
    return len(rows)


def print_summary(dashboard, database_path):
    securities = dashboard[dashboard["asset_type"] == "SECURITY"]
    cash = dashboard[dashboard["asset_type"] == "CASH"].iloc[0]

    print("\n" + "=" * 100)
    print("PORTFOLIO DASHBOARD DATASET COMPLETE")
    print("=" * 100)
    print(f"Database:              {database_path}")
    print(f"Dashboard date:         {dashboard['dashboard_date'].iloc[0]}")
    print(f"Security positions:     {len(securities):,}")
    print(f"Invested market value:  ${cash['total_invested_value']:,.2f}")
    print(f"Cash balance:           ${cash['cash_balance']:,.2f}")
    print(f"Cash weight:            {cash['cash_weight_pct']:,.2f}%")
    print(f"Total account value:    ${cash['total_account_value']:,.2f}")
    print(f"Unrealized P&L:         ${securities['unrealized_pnl'].sum():,.2f}")
    print(f"Daily position P&L:     ${securities['daily_pnl'].sum(min_count=1):,.2f}")

    display = securities.sort_values("account_weight_pct", ascending=False)[
        ["ticker", "market_value", "account_weight_pct", "unrealized_pnl", "daily_pnl"]
    ]
    print("\nACCOUNT ALLOCATION")
    print(
        display.to_string(
            index=False,
            float_format=lambda value: f"{value:,.2f}",
        )
    )
    print(
        f"{'CASH':>6}  {cash['market_value']:>12,.2f}  "
        f"{cash['account_weight_pct']:>18,.2f}  {0:>14,.2f}  {0:>10,.2f}"
    )
    print("=" * 100)
    print("account_weight_pct includes cash; invested_weight_pct excludes cash.")


def main():
    parser = argparse.ArgumentParser(
        description="Build a dashboard-ready portfolio dataset including cash."
    )
    parser.add_argument("--database", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--positions-table", default=DEFAULT_POSITIONS_TABLE)
    parser.add_argument("--prices-table", default=DEFAULT_PRICES_TABLE)
    parser.add_argument("--cash-table", default=DEFAULT_CASH_TABLE)
    parser.add_argument(
        "--as-of-date",
        help="Use prices on or before this date (YYYY-MM-DD). Defaults to latest.",
    )
    parser.add_argument(
        "--full-refresh",
        action="store_true",
        help="Delete and rebuild dashboard rows for the selected date.",
    )
    args = parser.parse_args()

    database_path = args.database.resolve()
    if not database_path.exists():
        raise FileNotFoundError(f"Database not found: {database_path}")

    with sqlite3.connect(database_path) as connection:
        validate_source_tables(
            connection, args.positions_table, args.prices_table, args.cash_table
        )
        schema = detect_schema(
            connection, args.positions_table, args.prices_table, args.cash_table
        )
        ensure_output_table(connection)
        positions = load_positions(connection, args.positions_table, schema)
        cash_balance, cash_source = load_cash(connection, args.cash_table, schema)
        prices = load_latest_prices(
            connection,
            args.prices_table,
            schema,
            positions["ticker"].tolist(),
            args.as_of_date,
        )
        dashboard = build_dashboard(
            positions, prices, cash_balance, cash_source, args.as_of_date
        )
        rows_written = upsert_dashboard(
            connection,
            dashboard,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            args.full_refresh,
        )
        connection.commit()

    if rows_written != len(dashboard):
        raise RuntimeError("Not all dashboard rows were written.")
    print_summary(dashboard, database_path)


if __name__ == "__main__":
    main()
