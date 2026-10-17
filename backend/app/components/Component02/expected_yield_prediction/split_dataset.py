
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
RAW_PATH = BASE_DIR / "data" / "raw" / "expected yield.csv"
SPLIT_DIR = BASE_DIR / "data" / "splits"

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
