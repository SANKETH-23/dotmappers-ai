"""
Data ingestion layer.
Loads the support tickets CSV into a pandas DataFrame
and provides helpers to inspect the data.
"""

import pandas as pd
from pathlib import Path

CSV_PATH = Path(__file__).parent / "support_tickets.csv"


def load_tickets(path: str | Path = CSV_PATH) -> pd.DataFrame:
    """Load the support tickets CSV and clean it up."""
    df = pd.read_csv(path)

    # Parse the timestamp column
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")

    # Standardise the customer rating column name
    if "customer_rating" in df.columns and "cust_rating" not in df.columns:
        df = df.rename(columns={"customer_rating": "cust_rating"})

    # Numeric coercion (blank strings become NaN)
    for col in ["response_time_hrs", "resolution_time_hrs", "cust_rating"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def summarize(df: pd.DataFrame) -> None:
    """Print a quick summary of the loaded data."""
    print(f"Rows: {len(df)}")
    print(f"Columns: {df.columns.tolist()}")
    print(f"\nDtypes:\n{df.dtypes}")
    print(f"\nNulls per column:\n{df.isnull().sum()}")
    print(f"\nUnique values:")
    print(f"  status:   {df['status'].unique().tolist()}")
    print(f"  priority: {df['priority'].unique().tolist()}")
    print(f"  category: {df['category'].unique().tolist()}")


if __name__ == "__main__":
    df = load_tickets()
    summarize(df)
    print("\nFirst 5 rows:")
    print(df.head())