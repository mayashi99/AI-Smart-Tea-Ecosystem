
import pandas as pd

from ml.utils.component02.expected_yield_prediction.paths import (
    PROCESSED_DATA_DIR,
    RAW_DATA_FILE,
)

RAW_PATH = RAW_DATA_FILE
SPLIT_DIR = PROCESSED_DATA_DIR

SPLIT_DIR.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(RAW_PATH)

# Sort chronologically before splitting
df = df.sort_values(
    ["Year", "Month_Number", "Week_Number", "Location"]
).reset_index(drop=True)

train = df[df["Year"].between(2016, 2023)].copy()
validation = df[df["Year"] == 2024].copy()
test = df[df["Year"] == 2025].copy()

# Save separate datasets
train.to_csv(SPLIT_DIR / "train.csv", index=False)
validation.to_csv(SPLIT_DIR / "validation.csv", index=False)
test.to_csv(SPLIT_DIR / "test.csv", index=False)

print("Chronological split completed")
print(f"Train:      {len(train)} rows")
print(f"Validation: {len(validation)} rows")
print(f"Test:       {len(test)} rows")

print("\nYear ranges:")
print(f"Train:      {train['Year'].min()}–{train['Year'].max()}")
print(f"Validation: {validation['Year'].unique()}")
print(f"Test:       {test['Year'].unique()}")

print("\nSaved files to:", SPLIT_DIR)
