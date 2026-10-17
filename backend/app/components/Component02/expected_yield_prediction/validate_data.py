
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "data" / "raw" / "expected yield.csv"

df = pd.read_csv(CSV_PATH)

print("=" * 55)
print("EXPECTED YIELD - VALIDATION")
print("=" * 55)

# 1. Year range
print("\nYear range:")
print(df["Year"].min(), "to", df["Year"].max())
print("Records per year:")
print(df.groupby("Year").size().to_string())

# 2. Month and week validity
print("\nInvalid month numbers:", 
      (~df["Month_Number"].between(1, 12)).sum())

print("Invalid week numbers:",
      (~df["Week_Number"].between(1, 4)).sum())

# 3. Records per location
print("\nRecords per location:")
print(df.groupby("Location").size().to_string())

# 4. Grown type mapping
print("\nGrown types by location:")
print(df.groupby("Location")["Grown_Type"].unique().to_string())

# 5. Duplicate location-week records
keys = ["Year", "Month_Number", "Week_Number", "Location"]
print("\nDuplicate location-week records:", df.duplicated(keys).sum())

# 6. Numeric ranges
numeric_cols = [
    "Production_kg", "Temperature", "Rainfall_mm",
    "Humidity", "Wind_Speed", "Solar_Radiation", "kg_per_Acre"
]

print("\nNumeric ranges:")
print(df[numeric_cols].describe().round(2).to_string())

print("\nValidation complete.")
