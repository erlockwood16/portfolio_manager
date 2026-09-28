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


def validate_sources(connection):
    requirements = {
        "portfolio_dashboard": {
            "dashboard_date", "asset_type", "ticker", "market_value",
            "account_weight_pct", "total_account_value"
        },
        "portfolio_targets": {
            "ticker", "target_group", "min_weight_pct", "target_weight_pct",
            "max_weight_pct", "thesis_status", "allow_sell"
        },
    }
    for table_name, required in requirements.items():
        if not table_exists(connection, table_name):
            raise RuntimeError(
                f"Required table '{table_name}' does not exist. "
                "Build the dashboard and portfolio targets first."
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


def minimum_trade_amount(connection, override):
    if override is not None:
        return float(override)
    if table_exists(connection, "advisor_policy"):
        row = connection.execute(
            """
            SELECT policy_value
            FROM advisor_policy
            WHERE policy_name = 'minimum_trade_amount'
            """
        ).fetchone()
        if row:
            return float(row[0])
    return DEFAULT_MINIMUM_TRADE


def load_positions_and_targets(connection, dashboard_date):
    rows = connection.execute(
        """
        SELECT
            UPPER(TRIM(d.ticker)) AS ticker,
            d.market_value,
            d.account_weight_pct,
            d.total_account_value,
            t.target_group,
            t.min_weight_pct,
            t.target_weight_pct,
            t.max_weight_pct,
            t.thesis_status,
            t.allow_sell,
            t.notes
        FROM portfolio_dashboard d
        LEFT JOIN portfolio_targets t
          ON UPPER(TRIM(t.ticker)) = UPPER(TRIM(d.ticker))
        WHERE d.dashboard_date = ?
          AND d.asset_type = 'SECURITY'
        ORDER BY d.account_weight_pct DESC
        """,
        (dashboard_date,),
    ).fetchall()

    if not rows:
        raise RuntimeError(f"No security positions found for {dashboard_date}.")

    missing = [row[0] for row in rows if row[4] is None]
    if missing:
        raise RuntimeError(
            "Missing portfolio_targets rows for current holdings: "
            + ", ".join(sorted(missing))
        )
    return rows


def build_recommendations(rows, dashboard_date, minimum_trade, drift_threshold):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    recommendations = []
    diagnostics = []

    for row in rows:
        (
            ticker, market_value, current_weight, total_account_value,
            target_group, minimum_weight, target_weight, maximum_weight,
            thesis_status, allow_sell, notes,
        ) = row

        current_weight = float(current_weight)
        target_weight = float(target_weight)
        maximum_weight = float(maximum_weight)
        total_account_value = float(total_account_value)
        excess_over_max = current_weight - maximum_weight
        target_gap = target_weight - current_weight

        action = "HOLD"
        amount = 0.0
        rationale = (
            f"Current {current_weight:.2f}%; target {target_weight:.2f}%; "
            f"maximum {maximum_weight:.2f}%."
        )

        # A sale is permitted only when the position is above its ticker-specific maximum.
        if excess_over_max > drift_threshold:
            amount_to_target = total_account_value * (current_weight - target_weight) / 100.0
            if not int(allow_sell):
                rationale += " Above maximum, but selling is disabled by portfolio policy."
            elif str(thesis_status).upper() not in {"APPROVED", "ACTIVE"}:
                rationale += f" Above maximum, but thesis status is {thesis_status}."
            elif amount_to_target < minimum_trade:
                rationale += f" Calculated reduction is below ${minimum_trade:,.2f} minimum."
            else:
                action = "SELL"
                amount = -amount_to_target
                rationale += (
                    f" Above policy maximum by {excess_over_max:.2f}%; "
                    f"reduce toward target by ${amount_to_target:,.2f}."
                )
        else:
            rationale += " Position is within its policy maximum; no sale recommended."

        if notes:
            rationale += f" Policy note: {notes}"

        priority = max(0.0, excess_over_max) * 15.0
        diagnostics.append(
            (action, ticker, target_group, current_weight, target_weight,
             maximum_weight, amount, priority)
        )

        # Store only actionable SELL recommendations. Stale SELL rows are removed on refresh.
        if action == "SELL":
            recommendations.append(
                (
                    dashboard_date, "SELL", ticker, current_weight,
                    target_weight, target_gap, amount, None, priority,
                    rationale, "PORTFOLIO_TARGETS_SELL_V2", timestamp,
                )
            )

    return recommendations, diagnostics


def save_recommendations(connection, rows, dashboard_date, full_refresh):
    # Always remove legacy SELL rows for this date so old max-position logic cannot leak
    # into the trade plan. This is intentional even without --full-refresh.
    connection.execute(
        """
        DELETE FROM advisor_recommendations
        WHERE recommendation_date = ?
          AND recommendation_type = 'SELL'
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
            current_weight_pct = excluded.current_weight_pct,
            target_weight_pct = excluded.target_weight_pct,
            weight_gap_pct = excluded.weight_gap_pct,
            recommendation_amount = excluded.recommendation_amount,
            score = excluded.score,
            priority_score = excluded.priority_score,
            rationale = excluded.rationale,
            status = 'PROPOSED',
            source = excluded.source,
            created_timestamp = excluded.created_timestamp
        """,
        rows,
    )


def print_summary(diagnostics, dashboard_date, minimum_trade):
    sells = [row for row in diagnostics if row[0] == "SELL"]
    print("\n" + "=" * 112)
    print("POLICY-BASED SELL RECOMMENDATIONS COMPLETE")
    print("=" * 112)
    print(f"Dashboard date:       {dashboard_date}")
    print(f"Minimum trade:        ${minimum_trade:,.2f}")
    print(f"Positions evaluated:  {len(diagnostics):,}")
    print(f"Sell recommendations: {len(sells):,}")
    print()
    print(
        f"{'Action':<10}{'Ticker':<9}{'Group':<20}{'Current %':>12}"
        f"{'Target %':>12}{'Max %':>10}{'Amount':>15}{'Priority':>12}"
    )
    print("-" * 112)
    for action, ticker, group, current, target, maximum, amount, priority in sorted(
        diagnostics, key=lambda item: item[7], reverse=True
    ):
        print(
            f"{action:<10}{ticker:<9}{group:<20}{current:>12.2f}"
            f"{target:>12.2f}{maximum:>10.2f}${amount:>14,.2f}{priority:>12.2f}"
        )
    print("=" * 112)
    print("A SELL is generated only when current weight exceeds ticker-specific max_weight_pct.")
    print("Legacy global 10% position-limit SELL rows are removed for the selected date.")
    print("Recommendations are decision support only and require review before execution.")


def main():
    parser = argparse.ArgumentParser(
        description="Generate sell recommendations using ticker-level portfolio targets."
    )
    parser.add_argument("--database", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--date", help="Dashboard date; defaults to latest.")
    parser.add_argument("--minimum-trade", type=float)
    parser.add_argument(
        "--drift-threshold",
        type=float,
        default=0.25,
        help="Required amount above max weight before a sale can be proposed.",
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
        inputs = load_positions_and_targets(connection, dashboard_date)
        recommendations, diagnostics = build_recommendations(
            inputs, dashboard_date, minimum_trade, args.drift_threshold
        )
        save_recommendations(
            connection, recommendations, dashboard_date, args.full_refresh
        )
        connection.commit()

    print_summary(diagnostics, dashboard_date, minimum_trade)


if __name__ == "__main__":
    main()
