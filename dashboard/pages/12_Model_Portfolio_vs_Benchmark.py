import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

# ==========================================
# Configuration
# ==========================================

ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = ROOT / "InvestmentAdvisor.db"
DEFAULT_BENCHMARKS = ["SPY", "QQQ", "VOO"]

st.set_page_config(page_title="Portfolio vs Benchmark", layout="wide")
st.title("📈 Model Portfolio vs Benchmark")
st.caption(
    "Compare historical total account value with normalized benchmark performance."
)


# ==========================================
# Data Access
# ==========================================

@st.cache_data(ttl=300)
def load_portfolio_snapshots(db_path: str) -> pd.DataFrame:
    with sqlite3.connect(db_path) as conn:
        columns = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(portfolio_snapshots)"
            ).fetchall()
        }

        if not columns:
            return pd.DataFrame()

        value_column = (
            "total_account_value"
            if "total_account_value" in columns
            else "portfolio_market_value"
        )

        cash_expression = (
            "cash_balance" if "cash_balance" in columns else "0.0"
        )

        query = f"""
        SELECT
            snapshot_date,
            {value_column} AS portfolio_value,
            portfolio_market_value,
            {cash_expression} AS cash_balance
        FROM portfolio_snapshots
        WHERE {value_column} IS NOT NULL
        ORDER BY snapshot_date
        """
        return pd.read_sql_query(query, conn)


@st.cache_data(ttl=300)
def load_benchmark_prices(db_path: str, tickers: tuple[str, ...]) -> pd.DataFrame:
    if not tickers:
        return pd.DataFrame()

    placeholders = ",".join("?" for _ in tickers)
    query = f"""
    SELECT ticker, price_date, close_price
    FROM prices
    WHERE UPPER(ticker) IN ({placeholders})
      AND close_price IS NOT NULL
    ORDER BY ticker, price_date
    """

    with sqlite3.connect(db_path) as conn:
        prices = pd.read_sql_query(query, conn, params=tickers)

    if prices.empty:
        return prices

    prices["ticker"] = prices["ticker"].str.upper()
    prices["price_date"] = pd.to_datetime(prices["price_date"], errors="coerce")
    prices["close_price"] = pd.to_numeric(
        prices["close_price"], errors="coerce"
    )
    prices = prices.dropna(subset=["price_date", "close_price"])

    # Protect the comparison from duplicate ticker/date price rows.
    prices = (
        prices.sort_values(["ticker", "price_date"])
        .drop_duplicates(["ticker", "price_date"], keep="last")
    )
    return prices


def prepare_portfolio(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return raw

    data = raw.copy()
    data["snapshot_date"] = pd.to_datetime(
        data["snapshot_date"], errors="coerce"
    )
    data["portfolio_value"] = pd.to_numeric(
        data["portfolio_value"], errors="coerce"
    )
    data = data.dropna(subset=["snapshot_date", "portfolio_value"])
    data = (
        data.sort_values("snapshot_date")
        .drop_duplicates("snapshot_date", keep="last")
    )
    return data[data["portfolio_value"] > 0].reset_index(drop=True)


def normalized_series(
    portfolio: pd.DataFrame,
    prices: pd.DataFrame,
    selected_benchmarks: list[str],
) -> tuple[pd.DataFrame, pd.Timestamp, pd.Timestamp]:
    start_date = portfolio["snapshot_date"].min()
    end_date = portfolio["snapshot_date"].max()

    portfolio_window = portfolio[
        portfolio["snapshot_date"].between(start_date, end_date)
    ].copy()
    base_value = portfolio_window.iloc[0]["portfolio_value"]
    portfolio_window["Portfolio"] = (
        portfolio_window["portfolio_value"] / base_value * 100
    )
    output = portfolio_window[["snapshot_date", "Portfolio"]].rename(
        columns={"snapshot_date": "date"}
    )

    for ticker in selected_benchmarks:
        benchmark = prices[prices["ticker"] == ticker].copy()
        benchmark = benchmark[
            benchmark["price_date"].between(start_date, end_date)
        ]
        if benchmark.empty:
            continue

        # Align benchmark observations to portfolio snapshot dates using the
        # latest market close on or before each snapshot date.
        aligned = pd.merge_asof(
            output[["date"]].sort_values("date"),
            benchmark[["price_date", "close_price"]].sort_values("price_date"),
            left_on="date",
            right_on="price_date",
            direction="backward",
        )
        aligned = aligned.dropna(subset=["close_price"])
        if aligned.empty:
            continue
        benchmark_base = aligned.iloc[0]["close_price"]
        values = aligned.set_index("date")["close_price"] / benchmark_base * 100
        output = output.merge(
            values.rename(ticker), left_on="date", right_index=True, how="left"
        )

    return output.set_index("date"), start_date, end_date


def total_return(series: pd.Series) -> float | None:
    clean = series.dropna()
    if len(clean) < 2 or clean.iloc[0] == 0:
        return None
    return (clean.iloc[-1] / clean.iloc[0] - 1) * 100


def max_drawdown(series: pd.Series) -> float | None:
    clean = series.dropna()
    if len(clean) < 2:
        return None
    drawdown = clean / clean.cummax() - 1
    return drawdown.min() * 100


def annualized_volatility(series: pd.Series) -> float | None:
    returns = series.dropna().pct_change().dropna()
    if len(returns) < 2:
        return None
    return returns.std(ddof=1) * (252 ** 0.5) * 100


def format_pct(value: float | None) -> str:
    return "N/A" if value is None or pd.isna(value) else f"{value:,.2f}%"


# ==========================================
# Load and Validate
# ==========================================

if not DB_PATH.exists():
    st.error(f"Database not found: {DB_PATH.name}")
    st.stop()

portfolio = prepare_portfolio(load_portfolio_snapshots(str(DB_PATH)))

if portfolio.empty:
    st.warning(
        "No portfolio snapshots are available. Run "
        "portfolio/capture_daily_snapshot.py first."
    )
    st.stop()

available_count = len(portfolio)
min_date = portfolio["snapshot_date"].min().date()
max_date = portfolio["snapshot_date"].max().date()

with st.sidebar:
    st.subheader("Comparison Settings")
    benchmarks = st.multiselect(
        "Benchmarks",
        options=DEFAULT_BENCHMARKS,
        default=DEFAULT_BENCHMARKS,
    )
    selected_start = st.date_input(
        "Start date",
        value=min_date,
        min_value=min_date,
        max_value=max_date,
    )
    selected_end = st.date_input(
        "End date",
        value=max_date,
        min_value=min_date,
        max_value=max_date,
    )

if selected_start > selected_end:
    st.error("Start date must be on or before end date.")
    st.stop()

portfolio = portfolio[
    portfolio["snapshot_date"].dt.date.between(selected_start, selected_end)
].copy()

if portfolio.empty:
    st.warning("No snapshots exist in the selected date range.")
    st.stop()

prices = load_benchmark_prices(str(DB_PATH), tuple(benchmarks))
comparison, start_date, end_date = normalized_series(
    portfolio, prices, benchmarks
)

# ==========================================
# Current Account Summary
# ==========================================

latest = portfolio.iloc[-1]
prior = portfolio.iloc[-2] if len(portfolio) > 1 else None
account_change = (
    latest["portfolio_value"] - prior["portfolio_value"]
    if prior is not None
    else None
)
portfolio_return = total_return(comparison["Portfolio"])

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Account Value", f"${latest['portfolio_value']:,.2f}")
c2.metric("Invested Market Value", f"${latest['portfolio_market_value']:,.2f}")
c3.metric("Cash Balance", f"${latest['cash_balance']:,.2f}")
c4.metric(
    "Portfolio Return",
    format_pct(portfolio_return),
    None if account_change is None else f"${account_change:,.2f} vs prior snapshot",
)

st.caption(
    f"Comparison window: {start_date.date()} through {end_date.date()} · "
    f"{len(portfolio):,} portfolio snapshots"
)

# ==========================================
# Performance Chart
# ==========================================

st.divider()
st.subheader("Growth of $100")

if len(comparison) < 2:
    st.info(
        "At least two snapshots are required to calculate return and compare "
        "performance over time. Continue capturing daily snapshots."
    )
else:
    chart_columns = [
        column for column in ["Portfolio", *benchmarks]
        if column in comparison.columns
    ]
    st.line_chart(comparison[chart_columns], use_container_width=True)

# ==========================================
# Metrics Table
# ==========================================

st.divider()
st.subheader("Performance Summary")

summary_rows = []
for name in ["Portfolio", *benchmarks]:
    if name not in comparison.columns:
        continue
    series = comparison[name]
    result_return = total_return(series)
    summary_rows.append(
        {
            "Series": name,
            "Total Return %": result_return,
            "Alpha vs Portfolio %": (
                portfolio_return - result_return
                if name != "Portfolio"
                and portfolio_return is not None
                and result_return is not None
                else None
            ),
            "Annualized Volatility %": annualized_volatility(series),
            "Max Drawdown %": max_drawdown(series),
            "Observations": int(series.notna().sum()),
        }
    )

summary_df = pd.DataFrame(summary_rows)
st.dataframe(
    summary_df.style.format(
        {
            "Total Return %": "{:.2f}%",
            "Alpha vs Portfolio %": "{:.2f}%",
            "Annualized Volatility %": "{:.2f}%",
            "Max Drawdown %": "{:.2f}%",
        },
        na_rep="N/A",
    ),
    hide_index=True,
    use_container_width=True,
)

# ==========================================
# Benchmark Availability and Export
# ==========================================

missing_benchmarks = [
    ticker for ticker in benchmarks if ticker not in comparison.columns
]
if missing_benchmarks:
    st.warning(
        "No usable benchmark prices were found in the selected date range for: "
        + ", ".join(missing_benchmarks)
        + ". Add these tickers to the universe and update the prices table."
    )

st.divider()
st.subheader("Comparison Data")
export_df = comparison.reset_index()
st.dataframe(export_df, hide_index=True, use_container_width=True)
st.download_button(
    "📥 Download Portfolio vs Benchmark CSV",
    data=export_df.to_csv(index=False).encode("utf-8"),
    file_name="portfolio_vs_benchmark.csv",
    mime="text/csv",
)

# ==========================================
# Methodology Notes
# ==========================================

st.divider()
st.subheader("Methodology and Caveats")
st.markdown(
    f"""
- The chart normalizes the portfolio and each benchmark to **100** at the first usable observation.
- Portfolio performance uses `total_account_value` when available; otherwise it falls back to invested market value.
- Benchmark prices are the latest close on or before each snapshot date.
- Cash is included in total account value but earns no assumed return.
- Deposits and withdrawals are **not yet cash-flow adjusted**. Therefore, changes in contributed or withdrawn capital can be mistaken for investment performance.
- At least two snapshots are required for a return; reliable volatility and drawdown statistics require substantially more observations.
- Loaded portfolio snapshots before filtering: **{available_count:,}**.
"""
)
