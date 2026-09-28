import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT / "InvestmentAdvisor.db"
DEFAULT_MINIMUM_TRADE = 100.0


def table_exists(connection, table_name):
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone() is not None


def table_columns(connection, table_name):
    return {
        row[1]
        for row in connection.execute(f'PRAGMA table_info("{table_name}")').fetchall()
    }


def ensure_output_table(connection):
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS advisor_recommendations (
            recommendation_date TEXT NOT NULL,
            recommendation_type TEXT NOT NULL,
            ticker TEXT NOT NULL,
            current_weight_pct REAL,
            target_weight_pct REAL,
            weight_gap_pct REAL,
            recommendation_amount REAL NOT NULL DEFAULT 0,
            score REAL,
            priority_score REAL NOT NULL DEFAULT 0,
            rationale TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PROPOSED',
            source TEXT NOT NULL,
            created_timestamp TEXT NOT NULL,
            PRIMARY KEY (recommendation_date, recommendation_type, ticker)
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_advisor_recommendations_date_type
        ON advisor_recommendations (recommendation_date, recommendation_type)
        """
    )


def validate_sources(connection):
    requirements = {
        "portfolio_dashboard": {
            "dashboard_date", "ticker", "asset_type", "market_value",
            "account_weight_pct", "total_account_value"
        },
        "portfolio_targets": {
            "ticker", "target_group", "min_weight_pct", "target_weight_pct",
            "max_weight_pct", "thesis_status", "allow_buy", "allow_sell"
        },
    }
    for table_name, required in requirements.items():
        if not table_exists(connection, table_name):
            raise RuntimeError(
                f"Required table '{table_name}' does not exist. "
                "Run build_portfolio_dashboard_dataset.py and build_portfolio_targets.py first."
            )
        missing = required - table_columns(connection, table_name)
        if missing:
            raise RuntimeError(
                f"{table_name} is missing columns: {', '.join(sorted(missing))}"
            )


def latest_dashboard_date(connection):
    row = connection.execute(
        "SELECT MAX(dashboard_date) FROM portfolio_dashboard"
    ).fetchone()
    if not row or not row[0]:
        raise RuntimeError("portfolio_dashboard is empty.")
    return row[0]


def minimum_trade_amount(connection, command_line_value):
    if command_line_value is not None:
        return command_line_value
    if table_exists(connection, "advisor_policy"):
        row = connection.execute(
            "SELECT policy_value FROM advisor_policy WHERE policy_name='minimum_trade_amount'"
        ).fetchone()
        if row:
            return float(row[0])
    return DEFAULT_MINIMUM_TRADE


def load_rebalance_inputs(connection, dashboard_date):
    rows = connection.execute(
        """
        SELECT
            d.ticker,
            d.asset_type,
            d.market_value,
            d.account_weight_pct,
            d.total_account_value,
            t.target_group,
            t.min_weight_pct,
            t.target_weight_pct,
            t.max_weight_pct,
            t.thesis_status,
            t.allow_buy,
            t.allow_sell,
            t.notes
        FROM portfolio_dashboard d
        LEFT JOIN portfolio_targets t
          ON UPPER(TRIM(t.ticker)) = UPPER(TRIM(d.ticker))
        WHERE d.dashboard_date = ?
        ORDER BY d.account_weight_pct DESC
        """,
        (dashboard_date,),
    ).fetchall()
    if not rows:
        raise RuntimeError(f"No dashboard rows found for {dashboard_date}.")

    missing_targets = [row[0] for row in rows if row[5] is None]
    if missing_targets:
        raise RuntimeError(
            "Missing portfolio targets for current holdings: "
            + ", ".join(sorted(missing_targets))
        )

    target_total = sum(float(row[7]) for row in rows)
    if abs(target_total - 100.0) > 0.01:
        raise RuntimeError(
            f"Current holding target weights total {target_total:.4f}%, not 100.00%."
        )
    return rows


def build_recommendations(rows, dashboard_date, minimum_trade, drift_threshold):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    recommendations = []

    for row in rows:
        (
            ticker, asset_type, market_value, current_weight, total_account_value,
            target_group, minimum_weight, target_weight, maximum_weight,
            thesis_status, allow_buy, allow_sell, notes,
        ) = row

        current_weight = float(current_weight)
        target_weight = float(target_weight)
        minimum_weight = float(minimum_weight)
        maximum_weight = float(maximum_weight)
        total_account_value = float(total_account_value)
        weight_gap = target_weight - current_weight
        proposed_amount = total_account_value * weight_gap / 100.0

        if current_weight < minimum_weight:
            action = "BUY" if asset_type != "CASH" else "INCREASE_CASH"
            outside_band = True
            rationale = (
                f"Below minimum {minimum_weight:.2f}%; target {target_weight:.2f}%."
            )
        elif current_weight > maximum_weight:
            action = "SELL" if asset_type != "CASH" else "DEPLOY_CASH"
            outside_band = True
            rationale = (
                f"Above maximum {maximum_weight:.2f}%; target {target_weight:.2f}%."
            )
        else:
            action = "HOLD"
            outside_band = False
            rationale = (
                f"Within {minimum_weight:.2f}% to {maximum_weight:.2f}% policy band."
            )

        if action in {"BUY", "INCREASE_CASH"} and not int(allow_buy):
            action = "HOLD"
            rationale += " Buying is disabled by policy."
        if action in {"SELL", "DEPLOY_CASH"} and not int(allow_sell):
            action = "HOLD"
            rationale += " Selling is disabled by policy."

        if str(thesis_status).upper() not in {"APPROVED", "ACTIVE"}:
            action = "HOLD"
            rationale += f" Thesis status is {thesis_status}."

        if abs(weight_gap) < drift_threshold:
            action = "HOLD"
            rationale += f" Drift is below {drift_threshold:.2f}% threshold."

        if abs(proposed_amount) < minimum_trade:
            action = "HOLD"
            rationale += f" Trade is below ${minimum_trade:,.2f} minimum."

        recommendation_amount = proposed_amount if action != "HOLD" else 0.0
        priority_score = abs(weight_gap) * (15.0 if outside_band else 5.0)
        if asset_type == "CASH" and outside_band:
            priority_score += 25.0

        rationale += f" Current {current_weight:.2f}%; gap {weight_gap:+.2f}%."
        if notes:
            rationale += f" Policy note: {notes}"

        recommendations.append(
            (
                dashboard_date,
                "REBALANCE",
                ticker,
                current_weight,
                target_weight,
                weight_gap,
                recommendation_amount,
                None,
                priority_score,
                f"{action}: {rationale}",
                "PORTFOLIO_TARGETS_V2",
                timestamp,
                action,
                target_group,
                minimum_weight,
                maximum_weight,
            )
        )
    return recommendations


def save_recommendations(connection, rows, dashboard_date, full_refresh):
    if full_refresh:
        connection.execute(
            """
            DELETE FROM advisor_recommendations
            WHERE recommendation_date = ? AND recommendation_type = 'REBALANCE'
            """,
            (dashboard_date,),
        )

    connection.executemany(
        """
        INSERT INTO advisor_recommendations (
            recommendation_date, recommendation_type, ticker,
            current_weight_pct, target_weight_pct, weight_gap_pct,
            recommendation_amount, score, priority_score, rationale,
            source, created_timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(recommendation_date, recommendation_type, ticker) DO UPDATE SET
            current_weight_pct=excluded.current_weight_pct,
            target_weight_pct=excluded.target_weight_pct,
            weight_gap_pct=excluded.weight_gap_pct,
            recommendation_amount=excluded.recommendation_amount,
            score=excluded.score,
            priority_score=excluded.priority_score,
            rationale=excluded.rationale,
            status='PROPOSED',
            source=excluded.source,
            created_timestamp=excluded.created_timestamp
        """,
        [row[:12] for row in rows],
    )


def print_summary(rows, dashboard_date, minimum_trade):
    actionable = [row for row in rows if row[12] != "HOLD"]
    holds = [row for row in rows if row[12] == "HOLD"]

    print("\n" + "=" * 118)
    print("POLICY-BASED REBALANCE RECOMMENDATIONS COMPLETE")
    print("=" * 118)
    print(f"Dashboard date:       {dashboard_date}")
    print(f"Minimum trade:        ${minimum_trade:,.2f}")
    print(f"Actionable positions: {len(actionable):,}")
    print(f"Hold positions:       {len(holds):,}")
    print()
    print(
        f"{'Action':<16}{'Ticker':<9}{'Group':<20}{'Current %':>12}"
        f"{'Target %':>12}{'Gap %':>11}{'Amount':>15}{'Priority':>12}"
    )
    print("-" * 118)
    for row in sorted(rows, key=lambda item: item[8], reverse=True):
        print(
            f"{row[12]:<16}{row[2]:<9}{row[13]:<20}{row[3]:>12.2f}"
            f"{row[4]:>12.2f}{row[5]:>11.2f}${row[6]:>14,.2f}{row[8]:>12.2f}"
        )
    print("=" * 118)
    print("Positive amounts indicate capital to add; negative amounts indicate capital to reduce.")
    print("Recommendations are decision support only and require review before execution.")


def main():
    parser = argparse.ArgumentParser(
        description="Generate policy-based rebalance recommendations from portfolio_targets."
    )
    parser.add_argument("--database", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--date", help="Dashboard date in YYYY-MM-DD format; defaults to latest.")
    parser.add_argument("--minimum-trade", type=float)
    parser.add_argument(
        "--drift-threshold",
        type=float,
        default=0.25,
        help="Minimum absolute target-weight gap before a trade can be proposed.",
    )
    parser.add_argument("--full-refresh", action="store_true")
    args = parser.parse_args()

    database_path = args.database.resolve()
    if not database_path.exists():
        raise FileNotFoundError(f"Database not found: {database_path}")
    if args.minimum_trade is not None and args.minimum_trade < 0:
        raise ValueError("--minimum-trade cannot be negative.")
    if args.drift_threshold < 0:
        raise ValueError("--drift-threshold cannot be negative.")

    with sqlite3.connect(database_path) as connection:
        ensure_output_table(connection)
        validate_sources(connection)
        dashboard_date = args.date or latest_dashboard_date(connection)
        minimum_trade = minimum_trade_amount(connection, args.minimum_trade)
        inputs = load_rebalance_inputs(connection, dashboard_date)
        recommendations = build_recommendations(
            inputs, dashboard_date, minimum_trade, args.drift_threshold
        )
        save_recommendations(
            connection, recommendations, dashboard_date, args.full_refresh
        )
        connection.commit()

    print_summary(recommendations, dashboard_date, minimum_trade)


if __name__ == "__main__":
    main()
