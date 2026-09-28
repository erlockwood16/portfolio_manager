import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT / "InvestmentAdvisor.db"
DEFAULT_POSITIONS_TABLE = "positions"
DEFAULT_PRICES_TABLE = "prices"


def table_exists(connection, table_name):
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone() is not None


def table_columns(connection, table_name):
    return {
        row[1] for row in connection.execute(
            f'PRAGMA table_info("{table_name}")'
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


def quote_identifier(value):
    return '"' + value.replace('"', '""') + '"'


def validate_source_tables(connection, positions_table, prices_table):
    for table_name in (positions_table, prices_table):
        if not table_exists(connection, table_name):
            raise RuntimeError(f"Required table '{table_name}' does not exist.")


def detect_schema(connection, positions_table, prices_table):
    position_columns = table_columns(connection, positions_table)
    price_columns = table_columns(connection, prices_table)

    schema = {
        "position_ticker": choose_column(
            position_columns, ["ticker", "symbol"], "position ticker"
        ),
        "quantity": choose_column(
            position_columns,
            ["quantity", "shares", "share_quantity", "current_quantity"],
            "position quantity",
        ),
        "cost_basis": choose_column(
            position_columns,
            ["cost_basis", "total_cost_basis", "position_cost_basis"],
            "position cost basis",
            required=False,
        ),
        "average_cost": choose_column(
            position_columns,
            ["average_cost", "avg_cost", "average_price", "avg_price"],
            "average cost",
            required=False,
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
    }

    if schema["cost_basis"] is None and schema["average_cost"] is None:
        raise RuntimeError(
            "The positions table must contain either total cost basis or average cost."
        )
    return schema


def ensure_output_table(connection):
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS portfolio_attribution (
            attribution_date TEXT NOT NULL,
            ticker TEXT NOT NULL,
            quantity REAL NOT NULL,
            current_price REAL NOT NULL,
            prior_price REAL,
            market_value REAL NOT NULL,
            cost_basis REAL,
            unrealized_pnl REAL,
            weight_pct REAL NOT NULL,
            daily_pnl REAL,
            contribution_pct REAL,
            price_date TEXT NOT NULL,
            prior_price_date TEXT,
            updated_timestamp TEXT NOT NULL,
            PRIMARY KEY (attribution_date, ticker)
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_portfolio_attribution_date
        ON portfolio_attribution (attribution_date DESC)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_portfolio_attribution_ticker_date
        ON portfolio_attribution (ticker, attribution_date DESC)
        """
    )


def load_positions(connection, positions_table, schema):
    ticker = quote_identifier(schema["position_ticker"])
    quantity = quote_identifier(schema["quantity"])

    if schema["cost_basis"]:
        cost_expression = f"SUM(COALESCE({quote_identifier(schema['cost_basis'])}, 0))"
    else:
        average_cost = quote_identifier(schema["average_cost"])
        cost_expression = f"SUM(COALESCE({quantity}, 0) * COALESCE({average_cost}, 0))"

    query = f"""
        SELECT
            UPPER(TRIM({ticker})) AS ticker,
            SUM(COALESCE({quantity}, 0)) AS quantity,
            {cost_expression} AS cost_basis
        FROM {quote_identifier(positions_table)}
        WHERE {ticker} IS NOT NULL
        GROUP BY UPPER(TRIM({ticker}))
        HAVING ABS(SUM(COALESCE({quantity}, 0))) > 0.00000001
        ORDER BY ticker
    """
    positions = pd.read_sql_query(query, connection)
    if positions.empty:
        raise RuntimeError("No open positions were found.")
    return positions


def load_prices(connection, prices_table, schema, tickers, as_of_date=None):
    placeholders = ",".join("?" for _ in tickers)
    ticker = quote_identifier(schema["price_ticker"])
    price_date = quote_identifier(schema["price_date"])
    close_price = quote_identifier(schema["close_price"])

    date_filter = ""
    parameters = list(tickers)
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
        raise RuntimeError("No price history was found for the open positions.")

    prices["price_date"] = pd.to_datetime(prices["price_date"], errors="coerce")
    prices["close_price"] = pd.to_numeric(prices["close_price"], errors="coerce")
    prices = prices.dropna(subset=["ticker", "price_date", "close_price"])
    prices = prices[prices["close_price"] > 0]
    prices = prices.drop_duplicates(["ticker", "price_date"], keep="last")
    return prices.sort_values(["ticker", "price_date"])


def calculate_attribution(positions, prices, requested_date=None):
    latest_rows = prices.groupby("ticker", as_index=False).tail(1).copy()
    prior_rows = prices.groupby("ticker", as_index=False).nth(-2).reset_index()

    latest_rows = latest_rows.rename(
        columns={"price_date": "price_date", "close_price": "current_price"}
    )
    prior_rows = prior_rows[["ticker", "price_date", "close_price"]].rename(
        columns={"price_date": "prior_price_date", "close_price": "prior_price"}
    )

    results = positions.merge(
        latest_rows[["ticker", "price_date", "current_price"]],
        on="ticker",
        how="left",
    ).merge(prior_rows, on="ticker", how="left")

    missing = results.loc[results["current_price"].isna(), "ticker"].tolist()
    if missing:
        print("WARNING - Missing current prices; excluded: " + ", ".join(missing))
    results = results.dropna(subset=["current_price"]).copy()
    if results.empty:
        raise RuntimeError("No open positions had usable current prices.")

    results["market_value"] = results["quantity"] * results["current_price"]
    total_market_value = results["market_value"].sum()
    if total_market_value == 0:
        raise RuntimeError("Total portfolio market value is zero.")

    results["unrealized_pnl"] = results["market_value"] - results["cost_basis"]
    results["weight_pct"] = results["market_value"] / total_market_value * 100.0
    results["daily_pnl"] = results["quantity"] * (
        results["current_price"] - results["prior_price"]
    )

    # Contribution is each holding's daily P&L divided by prior-day portfolio value.
    prior_portfolio_value = (
        results["quantity"] * results["prior_price"]
    ).sum(min_count=1)
    if pd.notna(prior_portfolio_value) and prior_portfolio_value != 0:
        results["contribution_pct"] = (
            results["daily_pnl"] / prior_portfolio_value * 100.0
        )
    else:
        results["contribution_pct"] = None

    if requested_date:
        attribution_date = requested_date
    else:
        attribution_date = results["price_date"].max().strftime("%Y-%m-%d")
    results["attribution_date"] = attribution_date
    results["price_date"] = results["price_date"].dt.strftime("%Y-%m-%d")
    results["prior_price_date"] = results["prior_price_date"].dt.strftime("%Y-%m-%d")
    return results.sort_values("daily_pnl", ascending=False).reset_index(drop=True)


def upsert_results(connection, results, timestamp, full_refresh=False):
    attribution_date = results["attribution_date"].iloc[0]
    if full_refresh:
        connection.execute(
            "DELETE FROM portfolio_attribution WHERE attribution_date = ?",
            (attribution_date,),
        )

    rows = []
    for row in results.itertuples(index=False):
        rows.append(
            (
                row.attribution_date,
                row.ticker,
                float(row.quantity),
                float(row.current_price),
                None if pd.isna(row.prior_price) else float(row.prior_price),
                float(row.market_value),
                None if pd.isna(row.cost_basis) else float(row.cost_basis),
                None if pd.isna(row.unrealized_pnl) else float(row.unrealized_pnl),
                float(row.weight_pct),
                None if pd.isna(row.daily_pnl) else float(row.daily_pnl),
                None if pd.isna(row.contribution_pct) else float(row.contribution_pct),
                row.price_date,
                None if pd.isna(row.prior_price_date) else row.prior_price_date,
                timestamp,
            )
        )

    connection.executemany(
        """
        INSERT INTO portfolio_attribution (
            attribution_date, ticker, quantity, current_price, prior_price,
            market_value, cost_basis, unrealized_pnl, weight_pct, daily_pnl,
            contribution_pct, price_date, prior_price_date, updated_timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(attribution_date, ticker) DO UPDATE SET
            quantity = excluded.quantity,
            current_price = excluded.current_price,
            prior_price = excluded.prior_price,
            market_value = excluded.market_value,
            cost_basis = excluded.cost_basis,
            unrealized_pnl = excluded.unrealized_pnl,
            weight_pct = excluded.weight_pct,
            daily_pnl = excluded.daily_pnl,
            contribution_pct = excluded.contribution_pct,
            price_date = excluded.price_date,
            prior_price_date = excluded.prior_price_date,
            updated_timestamp = excluded.updated_timestamp
        """,
        rows,
    )
    return len(rows)


def print_summary(results, database_path):
    total_market_value = results["market_value"].sum()
    total_unrealized_pnl = results["unrealized_pnl"].sum()
    total_daily_pnl = results["daily_pnl"].sum(min_count=1)

    print("\n" + "=" * 88)
    print("PORTFOLIO ATTRIBUTION COMPLETE")
    print("=" * 88)
    print(f"Database:             {database_path}")
    print(f"Attribution date:      {results['attribution_date'].iloc[0]}")
    print(f"Positions analyzed:    {len(results):,}")
    print(f"Total market value:    ${total_market_value:,.2f}")
    print(f"Unrealized P&L:        ${total_unrealized_pnl:,.2f}")
    if pd.notna(total_daily_pnl):
        print(f"Daily position P&L:    ${total_daily_pnl:,.2f}")

    display_columns = [
        "ticker", "market_value", "weight_pct", "daily_pnl", "contribution_pct"
    ]
    print("\nTOP CONTRIBUTORS")
    print(results[display_columns].head(10).to_string(index=False, float_format=lambda x: f"{x:,.4f}"))
    print("\nTOP DETRACTORS")
    print(results.sort_values("daily_pnl")[display_columns].head(10).to_string(index=False, float_format=lambda x: f"{x:,.4f}"))
    print("=" * 88)
    print("Attribution covers invested positions only; cash is excluded.")
    print("Daily P&L uses each ticker's two most recent available closing prices.")


def main():
    parser = argparse.ArgumentParser(
        description="Calculate current portfolio position attribution."
    )
    parser.add_argument("--database", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--positions-table", default=DEFAULT_POSITIONS_TABLE)
    parser.add_argument("--prices-table", default=DEFAULT_PRICES_TABLE)
    parser.add_argument(
        "--as-of-date",
        help="Use prices on or before this date (YYYY-MM-DD). Defaults to latest.",
    )
    parser.add_argument(
        "--full-refresh",
        action="store_true",
        help="Delete and rebuild attribution rows for the selected date.",
    )
    args = parser.parse_args()

    database_path = args.database.resolve()
    if not database_path.exists():
        raise FileNotFoundError(f"Database not found: {database_path}")

    with sqlite3.connect(database_path) as connection:
        validate_source_tables(connection, args.positions_table, args.prices_table)
        schema = detect_schema(connection, args.positions_table, args.prices_table)
        ensure_output_table(connection)
        positions = load_positions(connection, args.positions_table, schema)
        prices = load_prices(
            connection,
            args.prices_table,
            schema,
            positions["ticker"].tolist(),
            args.as_of_date,
        )
        results = calculate_attribution(positions, prices, args.as_of_date)
        rows_written = upsert_results(
            connection,
            results,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            args.full_refresh,
        )
        connection.commit()

    if rows_written != len(results):
        raise RuntimeError("Not all attribution rows were written.")
    print_summary(results, database_path)


if __name__ == "__main__":
    main()
