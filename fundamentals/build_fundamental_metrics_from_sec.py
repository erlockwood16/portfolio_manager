from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT / "InvestmentAdvisor.db"
OUTPUT_TABLE = "fundamental_metrics"

GROWTH_BOUNDS = {
    "revenue_growth": (-100.0, 500.0),
    "earnings_growth": (-500.0, 500.0),
    "asset_growth": (-100.0, 500.0),
}


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone() is not None


def table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {
        row[1]
        for row in conn.execute(
            f'PRAGMA table_info("{table_name}")'
        ).fetchall()
    }


def ensure_output_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {OUTPUT_TABLE} (
            ticker TEXT PRIMARY KEY,
            fiscal_year INTEGER,
            prior_fiscal_year INTEGER,
            revenue REAL,
            prior_revenue REAL,
            net_income REAL,
            prior_net_income REAL,
            assets REAL,
            prior_assets REAL,
            liabilities REAL,
            shareholders_equity REAL,
            revenue_growth REAL,
            earnings_growth REAL,
            asset_growth REAL,
            net_margin REAL,
            debt_ratio REAL,
            roa REAL,
            roe REAL,
            quality_score REAL,
            data_completeness_pct REAL,
            calculated_date TEXT,
            source TEXT
        )
        """
    )

    required = {
        "fiscal_year": "INTEGER",
        "prior_fiscal_year": "INTEGER",
        "revenue": "REAL",
        "prior_revenue": "REAL",
        "net_income": "REAL",
        "prior_net_income": "REAL",
        "assets": "REAL",
        "prior_assets": "REAL",
        "liabilities": "REAL",
        "shareholders_equity": "REAL",
        "revenue_growth": "REAL",
        "earnings_growth": "REAL",
        "asset_growth": "REAL",
        "net_margin": "REAL",
        "debt_ratio": "REAL",
        "roa": "REAL",
        "roe": "REAL",
        "quality_score": "REAL",
        "data_completeness_pct": "REAL",
        "calculated_date": "TEXT",
        "source": "TEXT",
    }

    existing = table_columns(conn, OUTPUT_TABLE)
    for column_name, data_type in required.items():
        if column_name not in existing:
            conn.execute(
                f'ALTER TABLE {OUTPUT_TABLE} '
                f'ADD COLUMN "{column_name}" {data_type}'
            )


def load_sec_history(conn: sqlite3.Connection) -> pd.DataFrame:
    if not table_exists(conn, "sec_financials"):
        raise RuntimeError("Required table 'sec_financials' does not exist.")

    required = {
        "ticker",
        "fiscal_year",
        "revenue",
        "net_income",
        "assets",
        "liabilities",
    }
    missing = required - table_columns(conn, "sec_financials")
    if missing:
        raise RuntimeError(
            "sec_financials is missing required columns: "
            + ", ".join(sorted(missing))
        )

    return pd.read_sql_query(
        """
        SELECT
            UPPER(TRIM(ticker)) AS ticker,
            CAST(fiscal_year AS INTEGER) AS fiscal_year,
            CAST(revenue AS REAL) AS revenue,
            CAST(net_income AS REAL) AS net_income,
            CAST(assets AS REAL) AS assets,
            CAST(liabilities AS REAL) AS liabilities
        FROM sec_financials
        WHERE ticker IS NOT NULL
          AND TRIM(ticker) <> ''
          AND fiscal_year IS NOT NULL
        ORDER BY ticker, fiscal_year DESC
        """,
        conn,
    )


def safe_growth(current: pd.Series, prior: pd.Series) -> pd.Series:
    current_numeric = pd.to_numeric(current, errors="coerce")
    prior_numeric = pd.to_numeric(prior, errors="coerce")

    valid_prior = prior_numeric.where(prior_numeric.abs() > 1e-12)
    growth = (current_numeric - prior_numeric) / valid_prior.abs() * 100.0
    return growth.replace([np.inf, -np.inf], np.nan)


def safe_ratio(
    numerator: pd.Series,
    denominator: pd.Series,
    denominator_must_be_positive: bool = True,
) -> pd.Series:
    numerator_numeric = pd.to_numeric(numerator, errors="coerce")
    denominator_numeric = pd.to_numeric(denominator, errors="coerce")

    if denominator_must_be_positive:
        valid_denominator = denominator_numeric.where(denominator_numeric > 0)
    else:
        valid_denominator = denominator_numeric.where(
            denominator_numeric.abs() > 1e-12
        )

    ratio = numerator_numeric / valid_denominator * 100.0
    return ratio.replace([np.inf, -np.inf], np.nan)


def percentile_score(series: pd.Series, higher_is_better: bool) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce").replace(
        [np.inf, -np.inf], np.nan
    )
    result = pd.Series(np.nan, index=series.index, dtype=float)
    valid = numeric.notna()

    if valid.any():
        result.loc[valid] = (
            numeric.loc[valid]
            .rank(
                method="average",
                pct=True,
                ascending=higher_is_better,
            )
            * 100.0
        )

    return result


def calculate_metrics(history: pd.DataFrame) -> pd.DataFrame:
    if history.empty:
        raise RuntimeError("sec_financials contains no usable rows.")

    numeric_columns = [
        "fiscal_year",
        "revenue",
        "net_income",
        "assets",
        "liabilities",
    ]
    for column in numeric_columns:
        history[column] = pd.to_numeric(history[column], errors="coerce")

    history = (
        history.sort_values(
            ["ticker", "fiscal_year"],
            ascending=[True, False],
        )
        .drop_duplicates(["ticker", "fiscal_year"], keep="first")
    )

    latest = history.groupby("ticker", sort=True).nth(0).reset_index()
    prior = history.groupby("ticker", sort=True).nth(1).reset_index()

    prior = prior.rename(
        columns={
            "fiscal_year": "prior_fiscal_year",
            "revenue": "prior_revenue",
            "net_income": "prior_net_income",
            "assets": "prior_assets",
            "liabilities": "prior_liabilities",
        }
    )

    prior_columns = [
        "ticker",
        "prior_fiscal_year",
        "prior_revenue",
        "prior_net_income",
        "prior_assets",
        "prior_liabilities",
    ]
    metrics = latest.merge(
        prior[prior_columns],
        on="ticker",
        how="left",
    )

    # Only compare consecutive fiscal years. Non-consecutive observations are
    # retained for current-period profitability but do not produce growth rates.
    consecutive = (
        metrics["prior_fiscal_year"].notna()
        & ((metrics["fiscal_year"] - metrics["prior_fiscal_year"]) == 1)
    )

    metrics["revenue_growth"] = safe_growth(
        metrics["revenue"], metrics["prior_revenue"]
    ).where(consecutive)
    metrics["earnings_growth"] = safe_growth(
        metrics["net_income"], metrics["prior_net_income"]
    ).where(consecutive)
    metrics["asset_growth"] = safe_growth(
        metrics["assets"], metrics["prior_assets"]
    ).where(consecutive)

    for column, (lower, upper) in GROWTH_BOUNDS.items():
        metrics[column] = metrics[column].clip(lower, upper)

    metrics["shareholders_equity"] = (
        metrics["assets"] - metrics["liabilities"]
    )
    metrics["net_margin"] = safe_ratio(
        metrics["net_income"], metrics["revenue"]
    )
    metrics["debt_ratio"] = safe_ratio(
        metrics["liabilities"], metrics["assets"]
    )
    metrics["roa"] = safe_ratio(
        metrics["net_income"], metrics["assets"]
    )
    metrics["roe"] = safe_ratio(
        metrics["net_income"], metrics["shareholders_equity"]
    )

    # Prevent extreme source values from dominating cross-sectional ranks.
    metrics["net_margin"] = metrics["net_margin"].clip(-200.0, 200.0)
    metrics["debt_ratio"] = metrics["debt_ratio"].clip(0.0, 300.0)
    metrics["roa"] = metrics["roa"].clip(-100.0, 100.0)
    metrics["roe"] = metrics["roe"].clip(-200.0, 200.0)

    quality_inputs = pd.DataFrame(
        {
            "margin": percentile_score(metrics["net_margin"], True),
            "roa": percentile_score(metrics["roa"], True),
            "roe": percentile_score(metrics["roe"], True),
            "leverage": percentile_score(metrics["debt_ratio"], False),
        },
        index=metrics.index,
    )
    metrics["quality_score"] = quality_inputs.mean(
        axis=1, skipna=True
    ).round(2)

    completeness_fields = [
        "revenue_growth",
        "earnings_growth",
        "asset_growth",
        "net_margin",
        "debt_ratio",
        "roa",
        "roe",
    ]
    metrics["data_completeness_pct"] = (
        metrics[completeness_fields].notna().mean(axis=1) * 100.0
    ).round(2)

    output_columns = [
        "ticker",
        "fiscal_year",
        "prior_fiscal_year",
        "revenue",
        "prior_revenue",
        "net_income",
        "prior_net_income",
        "assets",
        "prior_assets",
        "liabilities",
        "shareholders_equity",
        "revenue_growth",
        "earnings_growth",
        "asset_growth",
        "net_margin",
        "debt_ratio",
        "roa",
        "roe",
        "quality_score",
        "data_completeness_pct",
    ]
    return metrics[output_columns].copy()


def database_value(value):
    if pd.isna(value):
        return None
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return round(float(value), 6)
    return value


def upsert_metrics(
    conn: sqlite3.Connection,
    metrics: pd.DataFrame,
) -> int:
    calculated_date = datetime.today().strftime("%Y-%m-%d")
    source = "SEC companyfacts annual filings"

    payload = []
    columns_to_write = [
        "ticker",
        "fiscal_year",
        "prior_fiscal_year",
        "revenue",
        "prior_revenue",
        "net_income",
        "prior_net_income",
        "assets",
        "prior_assets",
        "liabilities",
        "shareholders_equity",
        "revenue_growth",
        "earnings_growth",
        "asset_growth",
        "net_margin",
        "debt_ratio",
        "roa",
        "roe",
        "quality_score",
        "data_completeness_pct",
    ]

    for row in metrics.itertuples(index=False, name=None):
        payload.append(
            tuple(database_value(value) for value in row)
            + (calculated_date, source)
        )

    conn.executemany(
        f"""
        INSERT INTO {OUTPUT_TABLE} (
            ticker,
            fiscal_year,
            prior_fiscal_year,
            revenue,
            prior_revenue,
            net_income,
            prior_net_income,
            assets,
            prior_assets,
            liabilities,
            shareholders_equity,
            revenue_growth,
            earnings_growth,
            asset_growth,
            net_margin,
            debt_ratio,
            roa,
            roe,
            quality_score,
            data_completeness_pct,
            calculated_date,
            source
        ) VALUES ({','.join('?' for _ in range(22))})
        ON CONFLICT(ticker) DO UPDATE SET
            fiscal_year = excluded.fiscal_year,
            prior_fiscal_year = excluded.prior_fiscal_year,
            revenue = excluded.revenue,
            prior_revenue = excluded.prior_revenue,
            net_income = excluded.net_income,
            prior_net_income = excluded.prior_net_income,
            assets = excluded.assets,
            prior_assets = excluded.prior_assets,
            liabilities = excluded.liabilities,
            shareholders_equity = excluded.shareholders_equity,
            revenue_growth = excluded.revenue_growth,
            earnings_growth = excluded.earnings_growth,
            asset_growth = excluded.asset_growth,
            net_margin = excluded.net_margin,
            debt_ratio = excluded.debt_ratio,
            roa = excluded.roa,
            roe = excluded.roe,
            quality_score = excluded.quality_score,
            data_completeness_pct = excluded.data_completeness_pct,
            calculated_date = excluded.calculated_date,
            source = excluded.source
        """,
        payload,
    )
    return len(payload)


def run_build(db_path: str | Path) -> int:
    database = Path(db_path).resolve()
    if not database.exists():
        raise FileNotFoundError(f"Database not found: {database}")

    with sqlite3.connect(database) as conn:
        ensure_output_schema(conn)
        history = load_sec_history(conn)
        metrics = calculate_metrics(history)
        processed = upsert_metrics(conn, metrics)
        conn.commit()

    counts = metrics[
        [
            "revenue_growth",
            "earnings_growth",
            "asset_growth",
            "net_margin",
            "debt_ratio",
            "roa",
            "roe",
            "quality_score",
        ]
    ].notna().sum()
    tickers_with_prior = int(metrics["prior_fiscal_year"].notna().sum())
    consecutive_history = int(
        (
            metrics["prior_fiscal_year"].notna()
            & (
                (metrics["fiscal_year"] - metrics["prior_fiscal_year"])
                == 1
            )
        ).sum()
    )

    print("\n" + "=" * 76)
    print("SEC FUNDAMENTAL METRICS BUILD COMPLETE")
    print("=" * 76)
    print(f"Database:                    {database}")
    print(f"Tickers processed:           {processed:,}")
    print(f"Tickers with prior history:  {tickers_with_prior:,}")
    print(f"Consecutive-year histories:  {consecutive_history:,}")
    print(f"Revenue growth populated:    {counts['revenue_growth']:,}")
    print(f"Earnings growth populated:   {counts['earnings_growth']:,}")
    print(f"Asset growth populated:      {counts['asset_growth']:,}")
    print(f"Net margin populated:        {counts['net_margin']:,}")
    print(f"Debt ratio populated:        {counts['debt_ratio']:,}")
    print(f"ROA populated:               {counts['roa']:,}")
    print(f"ROE populated:               {counts['roe']:,}")
    print(f"Quality scores populated:    {counts['quality_score']:,}")
    print("=" * 76)

    if consecutive_history == 0:
        print(
            "WARNING: No consecutive fiscal-year histories were found. "
            "Growth metrics require at least two annual rows per ticker."
        )

    return processed


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build growth, profitability, leverage, and quality metrics "
            "from annual SEC financial history."
        )
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DB_PATH,
    )
    args = parser.parse_args()
    run_build(args.database)


if __name__ == "__main__":
    main()
