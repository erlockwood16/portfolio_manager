from __future__ import annotations

import sqlite3
from datetime import datetime


def get_top_ranked_rows(conn: sqlite3.Connection, top_stocks: int = 20):
    """Load the highest-ranked stocks and deduplicate by ticker."""
    query = """
        SELECT
            a.ticker,
            a.overall_score,
            p.close_price
        FROM analytics_scores a
        LEFT JOIN (
            SELECT
                p1.ticker,
                p1.close_price
            FROM prices p1
            INNER JOIN (
                SELECT
                    ticker,
                    MAX(price_date) AS max_date
                FROM prices
                GROUP BY ticker
            ) latest
            ON p1.ticker = latest.ticker
            AND p1.price_date = latest.max_date
        ) p
        ON a.ticker = p.ticker
        WHERE a.overall_score IS NOT NULL
        ORDER BY a.overall_score DESC
        LIMIT ?
    """

    cursor = conn.cursor()
    cursor.execute(query, (top_stocks,))
    rows = cursor.fetchall()

    seen = set()
    unique_rows = []

    for row in rows:
        if row[0] not in seen:
            unique_rows.append(row)
            seen.add(row[0])

    return unique_rows


def create_recommended_allocations_table(conn: sqlite3.Connection) -> None:
    """Rebuild the recommended_allocations table."""
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS recommended_allocations")
    cursor.execute(
        """
        CREATE TABLE recommended_allocations (
            ticker TEXT PRIMARY KEY,
            overall_score REAL,
            allocation_pct REAL,
            position_value REAL,
            recommended_shares INTEGER,
            current_price REAL,
            generated_date TEXT
        )
        """
    )


def recommend_allocations(
    conn: sqlite3.Connection,
    portfolio_value: float = 25000,
    top_stocks: int = 20,
) -> int:
    """Build the recommended allocations table for the top-ranked stocks."""
    create_recommended_allocations_table(conn)

    rows = get_top_ranked_rows(conn, top_stocks=top_stocks)
    if not rows:
        print("\nNo ranked stocks found.")
        return 0

    total_score = sum(row[1] for row in rows if row[1] is not None)

    print("\n" + "=" * 80)
    print("RECOMMENDED ALLOCATIONS")
    print("=" * 80)

    allocated_value = 0.0
    cursor = conn.cursor()

    for ticker, score, price in rows:
        if price is None or price <= 0:
            print(f"Skipping {ticker}: invalid price")
            continue

        allocation_pct = round((score / total_score) * 100, 2) if total_score else 0.0
        position_value = round(portfolio_value * (allocation_pct / 100), 2)
        recommended_shares = int(position_value / price)
        allocated_value += position_value

        try:
            cursor.execute(
                """
                INSERT OR REPLACE INTO recommended_allocations
                (
                    ticker,
                    overall_score,
                    allocation_pct,
                    position_value,
                    recommended_shares,
                    current_price,
                    generated_date
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticker,
                    float(score),
                    float(allocation_pct),
                    float(position_value),
                    int(recommended_shares),
                    float(price),
                    datetime.today().strftime("%Y-%m-%d"),
                ),
            )
        except Exception as exc:
            print(f"\nINSERT FAILED: {ticker}")
            print(f"Score: {score}")
            print(f"Price: {price}")
            print(exc)
            raise

        print(
            f"{ticker:<8}"
            f"Score={score:<6.1f}"
            f"Alloc={allocation_pct:<6.2f}% "
            f"Shares={recommended_shares:<6}"
            f"Value=${position_value:,.0f}"
        )

    conn.commit()

    count = cursor.execute("SELECT COUNT(*) FROM recommended_allocations").fetchone()[0]

    print("\n" + "=" * 80)
    print(f"Allocations Created : {count}")
    print(f"Portfolio Value     : ${portfolio_value:,.0f}")
    print(f"Allocated Capital   : ${allocated_value:,.0f}")
    print(f"Remaining Cash      : ${portfolio_value - allocated_value:,.0f}")
    print("=" * 80)

    return count


def run_recommend_allocations(
    db_path: str = "InvestmentAdvisor.db",
    portfolio_value: float = 25000,
    top_stocks: int = 20,
) -> int:
    """Open a SQLite database and generate recommended allocations for the top-ranked stocks."""
    with sqlite3.connect(db_path) as conn:
        return recommend_allocations(
            conn,
            portfolio_value=portfolio_value,
            top_stocks=top_stocks,
        )
