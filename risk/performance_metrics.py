import sqlite3
import pandas as pd
import numpy as np

DB_PATH = "InvestmentAdvisor.db"


def load_snapshots():

    conn = sqlite3.connect(DB_PATH)

    query = """
    SELECT
        snapshot_date,
        total_account_value
    FROM portfolio_snapshots
    ORDER BY snapshot_date
    """

    df = pd.read_sql(query, conn)

    conn.close()

    return df


def calculate_total_return(df):

    starting_value = df.iloc[0]["total_account_value"]
    ending_value = df.iloc[-1]["total_account_value"]

    return (
        (ending_value - starting_value)
        / starting_value
    ) * 100


def calculate_max_drawdown(df):

    values = df["total_account_value"]

    running_max = values.cummax()

    drawdowns = (
        values - running_max
    ) / running_max

    return drawdowns.min() * 100


def calculate_sharpe_ratio(df):

    returns = (
        df["total_account_value"]
        .pct_change()
        .dropna()
    )

    if returns.std() == 0:
        return 0

    sharpe = (
        returns.mean()
        /
        returns.std()
    ) * np.sqrt(252)

    return sharpe


def main():

    df = load_snapshots()

    if len(df) < 2:

        print(
            "\nNeed at least 2 snapshots "
            "to calculate performance."
        )

        return

    total_return = calculate_total_return(df)

    max_drawdown = calculate_max_drawdown(df)

    sharpe_ratio = calculate_sharpe_ratio(df)

    print("\n" + "=" * 60)

    print("PORTFOLIO PERFORMANCE METRICS")

    print("=" * 60)

    print(
        f"Snapshots      : {len(df)}"
    )

    print(
        f"Total Return   : "
        f"{total_return:.2f}%"
    )

    print(
        f"Max Drawdown   : "
        f"{max_drawdown:.2f}%"
    )

    print(
        f"Sharpe Ratio   : "
        f"{sharpe_ratio:.2f}"
    )

    print("=" * 60)


if __name__ == "__main__":
    main()
