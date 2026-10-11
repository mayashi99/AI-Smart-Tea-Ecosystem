"""Prepare monthly Sri Lankan tea export volume from the supplied workbook."""
from pathlib import Path

import pandas as pd


ML_DIR = Path(__file__).resolve().parents[2]
RAW_FILE = ML_DIR / "datasets" / "raw" / "component04" / "Exports Volume 2016-2025 10 yrs .xlsx"
OUTPUT_DIR = ML_DIR / "datasets" / "processed" / "component04"
MONTHLY_FILE = OUTPUT_DIR / "export_demand_monthly.csv"


def load_monthly_export_demand(path: Path = RAW_FILE) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="Exports")
    required = {"Year", "Month", "Quantity (kg)"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Export workbook is missing columns: {sorted(missing)}")
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
    df["Month"] = pd.to_numeric(df["Month"], errors="coerce")
    df["Quantity (kg)"] = pd.to_numeric(
        df["Quantity (kg)"].astype(str).str.replace(",", "", regex=False), errors="coerce"
    )
    df = df.dropna(subset=["Year", "Month", "Quantity (kg)"])
    df = df[df["Quantity (kg)"].ge(0)]
    df["date"] = pd.to_datetime(dict(year=df["Year"].astype(int), month=df["Month"].astype(int), day=1), errors="coerce")
    monthly = df.dropna(subset=["date"]).groupby("date", as_index=False)["Quantity (kg)"].sum()
    monthly = monthly.rename(columns={"Quantity (kg)": "export_volume_kg"}).sort_values("date")
    if monthly.empty:
        raise ValueError("The workbook contains no valid monthly export quantities.")
    # Explicit zeroes preserve months with no recorded export rows.
    monthly = monthly.set_index("date").asfreq("MS", fill_value=0).rename_axis("date").reset_index()
    return monthly


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    monthly = load_monthly_export_demand()
    monthly.to_csv(MONTHLY_FILE, index=False)
    print(f"Saved {len(monthly)} months ({monthly.date.min().date()} to {monthly.date.max().date()}) to {MONTHLY_FILE}")


if __name__ == "__main__":
    main()
