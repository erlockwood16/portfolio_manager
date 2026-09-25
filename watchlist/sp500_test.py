import pandas as pd

sp500 = pd.read_csv(
    "data/sp500.csv"
)

print(sp500.head())

print(
    f"\nRows: {len(sp500)}"
)

print(
    f"Columns: {list(sp500.columns)}"
)
