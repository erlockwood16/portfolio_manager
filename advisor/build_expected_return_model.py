from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT / "InvestmentAdvisor.db"
OUTPUT_TABLE = "advisor_expected_returns"
MODEL_VERSION = "V3_MULTI_FACTOR_BLEND"
APPROVED_STATUSES = {"APPROVED", "ACTIVE", "READY", "BUY", "SELECTED"}

FACTOR_WEIGHTS = {
    "momentum_score": 0.25,
    "value_score": 0.15,
    "quality_score": 0.30,
    "growth_score": 0.30,
}


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()}


def first_column(available: set[str], candidates: list[str]) -> str | None:
    return next((candidate for candidate in candidates if candidate in available), None)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def ensure_output_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {OUTPUT_TABLE} (
            model_date TEXT NOT NULL,
            ticker TEXT NOT NULL,
            analytics_score REAL,
            normalized_score REAL,
            momentum_score REAL,
            value_score REAL,
            quality_score REAL,
            growth_score REAL,
            factor_count INTEGER NOT NULL DEFAULT 0,
            factor_component REAL NOT NULL DEFAULT 0,
            research_status TEXT,
            research_conviction REAL,
            current_weight_pct REAL,
            target_weight_pct REAL,
            target_gap_pct REAL,
            target_priority REAL,
            concentration_penalty REAL,
            sector_adjustment REAL,
            base_return_pct REAL NOT NULL,
            expected_return_pct REAL NOT NULL,
            confidence TEXT NOT NULL,
            opportunity_rank INTEGER,
            method TEXT NOT NULL,
            model_version TEXT NOT NULL,
            notes TEXT,
            updated_timestamp TEXT NOT NULL,
            PRIMARY KEY (model_date, ticker)
        )
        """
    )

    required = {
        "analytics_score": "REAL",
        "normalized_score": "REAL",
        "momentum_score": "REAL",
        "value_score": "REAL",
        "quality_score": "REAL",
        "growth_score": "REAL",
        "factor_count": "INTEGER NOT NULL DEFAULT 0",
        "factor_component": "REAL NOT NULL DEFAULT 0",
        "research_status": "TEXT",
        "research_conviction": "REAL",
        "current_weight_pct": "REAL",
        "target_weight_pct": "REAL",
        "target_gap_pct": "REAL",
        "target_priority": "REAL",
        "concentration_penalty": "REAL",
        "sector_adjustment": "REAL",
        "base_return_pct": "REAL",
        "expected_return_pct": "REAL",
        "confidence": "TEXT",
        "opportunity_rank": "INTEGER",
        "method": "TEXT",
        "model_version": "TEXT",
        "notes": "TEXT",
        "updated_timestamp": "TEXT",
    }
    existing = columns(conn, OUTPUT_TABLE)
    for name, data_type in required.items():
        if name not in existing:
            conn.execute(f'ALTER TABLE {OUTPUT_TABLE} ADD COLUMN "{name}" {data_type}')


def latest_dashboard_date(conn: sqlite3.Connection) -> str | None:
    if not table_exists(conn, "portfolio_dashboard"):
        return None
    row = conn.execute("SELECT MAX(dashboard_date) FROM portfolio_dashboard").fetchone()
    return row[0] if row else None


def load_universe(conn: sqlite3.Connection, model_date: str) -> list[str]:
    tickers: set[str] = set()

    if table_exists(conn, "portfolio_dashboard") and model_date:
        tickers.update(
            row[0]
            for row in conn.execute(
                """
                SELECT DISTINCT UPPER(TRIM(ticker))
                FROM portfolio_dashboard
                WHERE dashboard_date=?
                  AND UPPER(TRIM(ticker)) <> 'CASH'
                """,
                (model_date,),
            ).fetchall()
            if row[0]
        )

    if table_exists(conn, "research_queue"):
        available = columns(conn, "research_queue")
        ticker_col = first_column(available, ["ticker", "symbol"])
        status_col = first_column(available, ["status", "research_status", "approval_status"])
        if ticker_col and status_col:
            placeholders = ",".join("?" for _ in APPROVED_STATUSES)
            tickers.update(
                row[0]
                for row in conn.execute(
                    f"""
                    SELECT DISTINCT UPPER(TRIM("{ticker_col}"))
                    FROM research_queue
                    WHERE UPPER(TRIM("{status_col}")) IN ({placeholders})
                    """,
                    tuple(sorted(APPROVED_STATUSES)),
                ).fetchall()
                if row[0]
            )

    if table_exists(conn, "portfolio_targets"):
        tickers.update(
            row[0]
            for row in conn.execute(
                """
                SELECT DISTINCT UPPER(TRIM(ticker))
                FROM portfolio_targets
                WHERE UPPER(TRIM(ticker)) <> 'CASH'
                """
            ).fetchall()
            if row[0]
        )

    return sorted(tickers)


def load_scores(conn: sqlite3.Connection) -> dict[str, dict[str, float | None]]:
    if not table_exists(conn, "analytics_scores"):
        return {}

    available = columns(conn, "analytics_scores")
    ticker_col = first_column(available, ["ticker", "symbol"])
    date_col = first_column(available, ["score_date", "as_of_date", "date"])
    if not ticker_col:
        return {}

    factor_columns = [
        column
        for column in (
            "overall_score",
            "momentum_score",
            "value_score",
            "quality_score",
            "growth_score",
        )
        if column in available
    ]
    if not factor_columns:
        return {}

    select_fields = ", ".join(f'CAST("{column}" AS REAL)' for column in factor_columns)
    where = ""
    params: tuple[Any, ...] = ()
    if date_col:
        latest_row = conn.execute(
            f'SELECT MAX("{date_col}") FROM analytics_scores'
        ).fetchone()
        latest = latest_row[0] if latest_row else None
        if latest is not None:
            where = f' WHERE "{date_col}"=?'
            params = (latest,)

    rows = conn.execute(
        f'SELECT UPPER(TRIM("{ticker_col}")), {select_fields} '
        f'FROM analytics_scores{where}',
        params,
    ).fetchall()

    result: dict[str, dict[str, float | None]] = {}
    for row in rows:
        ticker = row[0]
        if not ticker:
            continue
        result[ticker] = {
            column: (None if value is None else float(value))
            for column, value in zip(factor_columns, row[1:])
        }
    return result


def load_research(conn: sqlite3.Connection) -> dict[str, tuple[str, float | None]]:
    if not table_exists(conn, "research_queue"):
        return {}

    available = columns(conn, "research_queue")
    ticker_col = first_column(available, ["ticker", "symbol"])
    status_col = first_column(available, ["status", "research_status", "approval_status"])
    conviction_col = first_column(
        available,
        ["conviction_score", "conviction", "research_score", "priority_score", "score"],
    )
    if not ticker_col or not status_col:
        return {}

    conviction_expr = f'CAST("{conviction_col}" AS REAL)' if conviction_col else "NULL"
    rows = conn.execute(
        f"""
        SELECT UPPER(TRIM("{ticker_col}")),
               UPPER(TRIM("{status_col}")),
               {conviction_expr}
        FROM research_queue
        """
    ).fetchall()

    result: dict[str, tuple[str, float | None]] = {}
    for ticker, status, conviction in rows:
        if not ticker:
            continue
        current = result.get(ticker)
        if current is None or status in APPROVED_STATUSES:
            result[ticker] = (
                status,
                None if conviction is None else float(conviction),
            )
    return result


def load_positions(conn: sqlite3.Connection, model_date: str) -> dict[str, float]:
    if not model_date or not table_exists(conn, "portfolio_dashboard"):
        return {}
    available = columns(conn, "portfolio_dashboard")
    if not {"ticker", "dashboard_date", "account_weight_pct"}.issubset(available):
        return {}

    asset_filter = ""
    if "asset_type" in available:
        asset_filter = " AND UPPER(TRIM(asset_type))='SECURITY'"
    rows = conn.execute(
        """
        SELECT UPPER(TRIM(ticker)), account_weight_pct
        FROM portfolio_dashboard
        WHERE dashboard_date=?
        """ + asset_filter,
        (model_date,),
    ).fetchall()
    return {ticker: float(weight) for ticker, weight in rows if ticker and weight is not None}


def load_targets(conn: sqlite3.Connection) -> dict[str, tuple[float | None, float | None, int, str | None]]:
    if not table_exists(conn, "portfolio_targets"):
        return {}
    available = columns(conn, "portfolio_targets")
    if "ticker" not in available:
        return {}

    target_expr = "target_weight_pct" if "target_weight_pct" in available else "NULL"
    max_expr = "max_weight_pct" if "max_weight_pct" in available else "NULL"
    allow_expr = "allow_buy" if "allow_buy" in available else "1"
    thesis_expr = "thesis_status" if "thesis_status" in available else "NULL"

    rows = conn.execute(
        f"""
        SELECT UPPER(TRIM(ticker)), {target_expr}, {max_expr}, {allow_expr}, {thesis_expr}
        FROM portfolio_targets
        WHERE UPPER(TRIM(ticker)) <> 'CASH'
        """
    ).fetchall()

    result = {}
    for ticker, target, max_weight, allow_buy, thesis in rows:
        if ticker:
            result[ticker] = (
                None if target is None else float(target),
                None if max_weight is None else float(max_weight),
                1 if allow_buy is None else int(allow_buy),
                None if thesis is None else str(thesis).upper(),
            )
    return result


def load_sector_adjustments(conn: sqlite3.Connection) -> dict[str, float]:
    if not (
        table_exists(conn, "portfolio_sector_allocation")
        and table_exists(conn, "advisor_sector_targets")
        and table_exists(conn, "asset_classification")
    ):
        return {}

    allocation_cols = columns(conn, "portfolio_sector_allocation")
    target_cols = columns(conn, "advisor_sector_targets")
    classification_cols = columns(conn, "asset_classification")
    if not {"sector", "account_weight_pct"}.issubset(allocation_cols):
        return {}
    if not {"sector", "target_weight_pct"}.issubset(target_cols):
        return {}
    if not {"ticker", "sector"}.issubset(classification_cols):
        return {}

    allocation_date_col = first_column(allocation_cols, ["allocation_date", "as_of_date", "date"])
    allocation_where = ""
    allocation_params: tuple[Any, ...] = ()
    if allocation_date_col:
        latest = conn.execute(
            f'SELECT MAX("{allocation_date_col}") FROM portfolio_sector_allocation'
        ).fetchone()[0]
        if latest is not None:
            allocation_where = f' WHERE "{allocation_date_col}"=?'
            allocation_params = (latest,)

    current = {
        sector: float(weight)
        for sector, weight in conn.execute(
            "SELECT sector, account_weight_pct FROM portfolio_sector_allocation"
            + allocation_where,
            allocation_params,
        ).fetchall()
        if sector and weight is not None
    }
    targets = {
        sector: float(weight)
        for sector, weight in conn.execute(
            "SELECT sector, target_weight_pct FROM advisor_sector_targets"
        ).fetchall()
        if sector and weight is not None
    }

    classification_date_col = first_column(
        classification_cols, ["classification_date", "as_of_date", "date"]
    )
    classification_where = ""
    classification_params: tuple[Any, ...] = ()
    if classification_date_col:
        latest = conn.execute(
            f'SELECT MAX("{classification_date_col}") FROM asset_classification'
        ).fetchone()[0]
        if latest is not None:
            classification_where = f' WHERE "{classification_date_col}"=?'
            classification_params = (latest,)

    ticker_sector = {
        ticker: sector
        for ticker, sector in conn.execute(
            "SELECT UPPER(TRIM(ticker)), sector FROM asset_classification"
            + classification_where,
            classification_params,
        ).fetchall()
        if ticker and sector
    }

    adjustments = {}
    for ticker, sector in ticker_sector.items():
        if sector in targets:
            gap = targets[sector] - current.get(sector, 0.0)
            adjustments[ticker] = clamp(gap * 0.10, -1.0, 1.0)
    return adjustments


def weighted_factor_component(
    factor_data: dict[str, float | None], sensitivity: float
) -> tuple[float, int, dict[str, float | None]]:
    factors = {
        name: (
            None
            if factor_data.get(name) is None
            else clamp(float(factor_data[name]), 0.0, 100.0)
        )
        for name in FACTOR_WEIGHTS
    }
    available_weight = sum(
        FACTOR_WEIGHTS[name] for name, value in factors.items() if value is not None
    )
    if available_weight == 0:
        return 0.0, 0, factors

    weighted_deviation = sum(
        (value - 50.0) * FACTOR_WEIGHTS[name]
        for name, value in factors.items()
        if value is not None
    ) / available_weight
    component = weighted_deviation * sensitivity
    return component, sum(value is not None for value in factors.values()), factors


def confidence_level(
    factor_count: int,
    approved: bool,
    conviction_present: bool,
    target_present: bool,
) -> str:
    evidence_points = factor_count + int(approved) + int(conviction_present) + int(target_present)
    if factor_count >= 3 and evidence_points >= 5:
        return "HIGH"
    if factor_count >= 2 or evidence_points >= 3:
        return "MEDIUM"
    return "LOW"


def build_rows(
    tickers: list[str],
    model_date: str,
    scores: dict[str, dict[str, float | None]],
    research: dict[str, tuple[str, float | None]],
    positions: dict[str, float],
    targets: dict[str, tuple[float | None, float | None, int, str | None]],
    sector_adjustments: dict[str, float],
    base_return: float,
    score_sensitivity: float,
    conviction_sensitivity: float,
    target_sensitivity: float,
    concentration_sensitivity: float,
    min_return: float,
    max_return: float,
) -> list[tuple[Any, ...]]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    records: list[dict[str, Any]] = []

    for ticker in tickers:
        factor_data = scores.get(ticker, {})
        overall = factor_data.get("overall_score")
        normalized = 50.0 if overall is None else clamp(float(overall), 0.0, 100.0)
        factor_component, factor_count, factors = weighted_factor_component(
            factor_data, score_sensitivity
        )

        status, raw_conviction = research.get(ticker, (None, None))
        approved = status in APPROVED_STATUSES
        conviction = (
            clamp(float(raw_conviction), 0.0, 100.0)
            if raw_conviction is not None
            else (60.0 if approved else 50.0)
        )
        conviction_component = (
            (conviction - 50.0) * conviction_sensitivity if approved else 0.0
        )

        current = positions.get(ticker, 0.0)
        target_data = targets.get(ticker)
        target = target_data[0] if target_data else None
        max_weight = target_data[1] if target_data else None
        allow_buy = target_data[2] if target_data else 1
        thesis = target_data[3] if target_data else None

        gap = target - current if target is not None else None
        target_priority = (
            clamp(gap * target_sensitivity, -2.0, 2.0) if gap is not None else 0.0
        )
        concentration_penalty = 0.0
        if max_weight is not None and current > max_weight:
            concentration_penalty = -clamp(
                (current - max_weight) * concentration_sensitivity, 0.0, 3.0
            )

        sector_component = sector_adjustments.get(ticker, 0.0)
        policy_penalty = -1.0 if (not allow_buy or (thesis and thesis not in {"APPROVED", "ACTIVE"})) else 0.0

        expected = clamp(
            base_return
            + factor_component
            + conviction_component
            + target_priority
            + concentration_penalty
            + sector_component
            + policy_penalty,
            min_return,
            max_return,
        )

        confidence = confidence_level(
            factor_count,
            approved,
            raw_conviction is not None,
            target_data is not None,
        )
        notes = (
            f"Base {base_return:.2f}%; factors {factor_component:+.2f}% "
            f"(momentum={factors['momentum_score']}, value={factors['value_score']}, "
            f"quality={factors['quality_score']}, growth={factors['growth_score']}); "
            f"conviction {conviction_component:+.2f}%; target {target_priority:+.2f}%; "
            f"concentration {concentration_penalty:+.2f}%; sector {sector_component:+.2f}%; "
            f"policy {policy_penalty:+.2f}%. Relative decision-support estimate, not a forecast."
        )

        records.append(
            {
                "model_date": model_date,
                "ticker": ticker,
                "analytics_score": overall,
                "normalized_score": normalized,
                "momentum_score": factors["momentum_score"],
                "value_score": factors["value_score"],
                "quality_score": factors["quality_score"],
                "growth_score": factors["growth_score"],
                "factor_count": factor_count,
                "factor_component": factor_component,
                "research_status": status,
                "research_conviction": conviction,
                "current_weight_pct": current,
                "target_weight_pct": target,
                "target_gap_pct": gap,
                "target_priority": target_priority,
                "concentration_penalty": concentration_penalty,
                "sector_adjustment": sector_component,
                "base_return_pct": base_return,
                "expected_return_pct": expected,
                "confidence": confidence,
                "method": MODEL_VERSION,
                "model_version": MODEL_VERSION,
                "notes": notes,
                "updated_timestamp": now,
            }
        )

    records.sort(key=lambda item: (-item["expected_return_pct"], item["ticker"]))
    for rank, record in enumerate(records, start=1):
        record["opportunity_rank"] = rank

    order = [
        "model_date", "ticker", "analytics_score", "normalized_score",
        "momentum_score", "value_score", "quality_score", "growth_score",
        "factor_count", "factor_component", "research_status", "research_conviction",
        "current_weight_pct", "target_weight_pct", "target_gap_pct", "target_priority",
        "concentration_penalty", "sector_adjustment", "base_return_pct",
        "expected_return_pct", "confidence", "opportunity_rank", "method",
        "model_version", "notes", "updated_timestamp",
    ]
    return [tuple(record[column] for column in order) for record in records]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Expected return model V3 using multi-factor analytics and portfolio policy."
    )
    parser.add_argument("--database", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--date", help="Portfolio dashboard date; defaults to latest.")
    parser.add_argument("--base-return", type=float, default=6.0)
    parser.add_argument("--score-sensitivity", type=float, default=0.08)
    parser.add_argument("--conviction-sensitivity", type=float, default=0.04)
    parser.add_argument("--target-sensitivity", type=float, default=0.20)
    parser.add_argument("--concentration-sensitivity", type=float, default=0.25)
    parser.add_argument("--min-return", type=float, default=-10.0)
    parser.add_argument("--max-return", type=float, default=20.0)
    parser.add_argument("--full-refresh", action="store_true")
    args = parser.parse_args()

    database = args.database.resolve()
    if not database.exists():
        raise FileNotFoundError(f"Database not found: {database}")

    with sqlite3.connect(database) as conn:
        ensure_output_table(conn)
        model_date = args.date or latest_dashboard_date(conn) or datetime.now().strftime("%Y-%m-%d")
        tickers = load_universe(conn, model_date)
        if not tickers:
            raise RuntimeError(
                "No current holdings, portfolio targets, or approved research ideas were found."
            )

        rows = build_rows(
            tickers=tickers,
            model_date=model_date,
            scores=load_scores(conn),
            research=load_research(conn),
            positions=load_positions(conn, model_date),
            targets=load_targets(conn),
            sector_adjustments=load_sector_adjustments(conn),
            base_return=args.base_return,
            score_sensitivity=args.score_sensitivity,
            conviction_sensitivity=args.conviction_sensitivity,
            target_sensitivity=args.target_sensitivity,
            concentration_sensitivity=args.concentration_sensitivity,
            min_return=args.min_return,
            max_return=args.max_return,
        )

        if args.full_refresh:
            conn.execute(f"DELETE FROM {OUTPUT_TABLE} WHERE model_date=?", (model_date,))

        conn.executemany(
            f"""
            INSERT INTO {OUTPUT_TABLE} (
                model_date, ticker, analytics_score, normalized_score,
                momentum_score, value_score, quality_score, growth_score,
                factor_count, factor_component, research_status, research_conviction,
                current_weight_pct, target_weight_pct, target_gap_pct, target_priority,
                concentration_penalty, sector_adjustment, base_return_pct,
                expected_return_pct, confidence, opportunity_rank, method,
                model_version, notes, updated_timestamp
            ) VALUES ({','.join('?' for _ in range(26))})
            ON CONFLICT(model_date, ticker) DO UPDATE SET
                analytics_score=excluded.analytics_score,
                normalized_score=excluded.normalized_score,
                momentum_score=excluded.momentum_score,
                value_score=excluded.value_score,
                quality_score=excluded.quality_score,
                growth_score=excluded.growth_score,
                factor_count=excluded.factor_count,
                factor_component=excluded.factor_component,
                research_status=excluded.research_status,
                research_conviction=excluded.research_conviction,
                current_weight_pct=excluded.current_weight_pct,
                target_weight_pct=excluded.target_weight_pct,
                target_gap_pct=excluded.target_gap_pct,
                target_priority=excluded.target_priority,
                concentration_penalty=excluded.concentration_penalty,
                sector_adjustment=excluded.sector_adjustment,
                base_return_pct=excluded.base_return_pct,
                expected_return_pct=excluded.expected_return_pct,
                confidence=excluded.confidence,
                opportunity_rank=excluded.opportunity_rank,
                method=excluded.method,
                model_version=excluded.model_version,
                notes=excluded.notes,
                updated_timestamp=excluded.updated_timestamp
            """,
            rows,
        )
        conn.commit()

    print(f"EXPECTED RETURN MODEL V3 | {model_date} | {len(rows)} securities")
    print("Rank Ticker   Expected %  Confidence  Overall  Factors  Research")
    print("-" * 78)
    for row in rows:
        overall_text = "N/A" if row[2] is None else f"{row[2]:.2f}"
        print(
            f"{row[21]:>4} {row[1]:<8} {row[19]:>10.2f}  {row[20]:<10} "
            f"{overall_text:>7}  {row[8]:>7}  {row[10] or 'NONE'}"
        )
    print(
        "\nCaveat: expected returns are transparent relative decision-support estimates "
        "derived from available factors, research, targets, concentration, and sector gaps; "
        "they are not market forecasts or guarantees."
    )


if __name__ == "__main__":
    main()
