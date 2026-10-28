
import pandas as pd

from ml.utils.component02.expected_yield_prediction.paths import RAW_DATA_FILE

# Project paths
CSV_PATH = RAW_DATA_FILE

print("=" * 60)
print("EXPECTED YIELD DATA QUALITY CHECK")
print("=" * 60)

# Check whether the CSV exists
if not CSV_PATH.exists():
    raise FileNotFoundError(f"CSV file not found: {CSV_PATH}")

# Load original dataset
df = pd.read_csv(CSV_PATH)

print(f"\nDataset shape: {df.shape[0]} rows, {df.shape[1]} columns")

print("\n--- Column Names ---")
print(df.columns.tolist())

print("\n--- Data Types ---")
print(df.dtypes)

print("\n--- First 5 Rows ---")
print(df.head().to_string(index=False))

print("\n--- Missing Values ---")
print(df.isnull().sum().to_string())

print(f"\nDuplicate rows: {df.duplicated().sum()}")

# Check target column
target = "kg_per_Acre"

if target in df.columns:
    print(f"\n--- Target: {target} ---")
    print(df[target].describe())

    print(f"\nNegative target values: {(df[target] < 0).sum()}")
    print(f"Zero target values: {(df[target] == 0).sum()}")
else:
    print(f"\nWARNING: Target column '{target}' was not found.")
    print("Check the actual column names printed above.")

print("\n--- Data Quality Check Complete ---")
