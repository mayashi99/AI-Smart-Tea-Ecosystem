"""Read monthly auction price and quantity from the combined workbook."""
from pathlib import Path

import pandas as pd


ML_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = ML_DIR / "datasets" / "raw" / "component04"
RAW_FILE = RAW_DIR / "Combined_Sales_Quantity_and_Price_Single_Sheet_2016_2026.xlsx"
OUTPUT_DIR = ML_DIR / "datasets" / "processed" / "component04"
MONTHLY_FILE = OUTPUT_DIR / "combined_auction_price_monthly.csv"


def load_monthly_data(path: Path = RAW_FILE) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="Combined Sales Data")
    required = {"Year", "Month Number", "Monthly Total", "Monthly Average Price (Rs/kg)"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Combined auction workbook is missing columns: {sorted(missing)}")
    for column in ("Year", "Month Number", "Monthly Total", "Monthly Average Price (Rs/kg)"):
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df = df.dropna(subset=list(required))
    df["date"] = pd.to_datetime(
        dict(year=df["Year"].astype(int), month=df["Month Number"].astype(int), day=1),
        errors="coerce",
    )
    df = df.dropna(subset=["date"])
    # Weekly rows repeat these monthly aggregates, so retain one row per month.
    monthly = df.sort_values(["date", "Week Number"]).drop_duplicates("date", keep="first")
    monthly = monthly[["date", "Monthly Total", "Monthly Average Price (Rs/kg)"]].rename(
        columns={"Monthly Total": "monthly_sales_quantity", "Monthly Average Price (Rs/kg)": "avg_price_lkr"}
    )
    monthly = monthly.sort_values("date").set_index("date").asfreq("MS")
    if monthly.isna().any().any():
        raise ValueError("Monthly auction data has missing months or values; fill them before training.")
    if len(monthly) < 60:
        raise ValueError(f"Need at least 60 monthly observations, got {len(monthly)}")
    return monthly.reset_index()


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    monthly = load_monthly_data()
    monthly.to_csv(MONTHLY_FILE, index=False)
    print(f"Saved {len(monthly)} monthly prices ({monthly.date.min().date()} to {monthly.date.max().date()})")


if __name__ == "__main__":
    main()
