import os
from pathlib import Path

import pandas as pd


ML_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = ML_DIR / "datasets" / "raw" / "component04"
OUTPUT_DIR = ML_DIR / "datasets" / "processed" / "component04"

INPUT_CANDIDATES = [
    RAW_DIR / "tea_auction_all_15_full_data.xlsx",
    RAW_DIR / "auction_price_all_15years.xlsx",
]
INPUT_FILE = next((path for path in INPUT_CANDIDATES if path.exists()), INPUT_CANDIDATES[0])

CLEAN_FILE = OUTPUT_DIR / "auction_price_clean.csv"
MONTHLY_FILE = OUTPUT_DIR / "auction_price_lstm.csv"
TRAIN_FILE = OUTPUT_DIR / "auction_price_lstm_train.csv"
TEST_FILE = OUTPUT_DIR / "auction_price_lstm_test.csv"

TRAIN_RATIO = 0.8
MAX_VALID_AVG_PRICE_LKR = 5000


def clean_numeric_value(value):
    return pd.to_numeric(str(value).replace(",", "").strip(), errors="coerce")


def clean_price_value(value):
    price = clean_numeric_value(value)
    if pd.isna(price) or price <= 0 or price > MAX_VALID_AVG_PRICE_LKR:
        return pd.NA
    return price


def clean_number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str).str.replace(",", "", regex=False).str.strip(),
        errors="coerce",
    )


def normalize_zone(series: pd.Series) -> pd.Series:
    return (
        series.fillna("Total")
        .astype(str)
        .str.strip()
        .replace(
            {
                "High Grown": "High Growns",
                "Medium Grown": "Medium Growns",
                "Low Grown": "Low Growns",
                "High grown": "High Growns",
                "Medium grown": "Medium Growns",
                "Low grown": "Low Growns",
                "nan": "Total",
            }
        )
    )


def load_raw_dataset(path: Path) -> pd.DataFrame:
    print(f"Reading dataset from: {path}")
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)

    excel_file = pd.ExcelFile(path)
    sheet_name = None
    for candidate in ["Tea Auction Data", "Sheet1", 0]:
        if candidate in excel_file.sheet_names:
            sheet_name = candidate
            break

    return pd.read_excel(path, sheet_name=sheet_name)


def build_zone_long_format(df: pd.DataFrame) -> pd.DataFrame:
    prepared = df.copy()
    prepared = prepared.dropna(axis=1, how="all").drop_duplicates()
    prepared["auction_date"] = pd.to_datetime(prepared["auction_date"], errors="coerce")

    zone_columns = {
        "High Growns": ("auction_high_grown_quantity", "high_grown_avg_price"),
        "Medium Growns": ("auction_medium_grown_quantity", "medium_grown_avg_price"),
        "Low Growns": ("auction_low_grown_quantity", "low_grown_avg_price"),
    }

    rows = []
    for _, row in prepared.iterrows():
        auction_date = row["auction_date"]
        if pd.isna(auction_date):
            continue

        for zone_name, (quantity_col, price_col) in zone_columns.items():
            quantity = clean_numeric_value(row.get(quantity_col))
            price = clean_price_value(row.get(price_col))
            if pd.notna(quantity) and pd.notna(price):
                rows.append(
                    {
                        "auction_date": auction_date,
                        "growing_zone": zone_name,
                        "quantity_kg": quantity,
                        "avg_price_lkr": price,
                    }
                )

        total_quantity = clean_numeric_value(row.get("total_quantity"))
        if pd.notna(total_quantity):
            zone_weights = []
            zone_prices = []
            for zone_name, (quantity_col, price_col) in zone_columns.items():
                quantity = clean_numeric_value(row.get(quantity_col))
                price = clean_price_value(row.get(price_col))
                if pd.notna(quantity) and pd.notna(price):
                    zone_weights.append(quantity)
                    zone_prices.append(price)

            if zone_weights and sum(zone_weights) > 0:
                weighted_price = sum(price * weight for price, weight in zip(zone_prices, zone_weights)) / sum(zone_weights)
                rows.append(
                    {
                        "auction_date": auction_date,
                        "growing_zone": "Total",
                        "quantity_kg": total_quantity,
                        "avg_price_lkr": weighted_price,
                    }
                )

    long_df = pd.DataFrame(rows)
    if long_df.empty:
        return pd.DataFrame(columns=["auction_date", "growing_zone", "quantity_kg", "avg_price_lkr"])

    long_df = long_df.dropna(subset=["auction_date", "growing_zone", "avg_price_lkr"])
    long_df = long_df.sort_values(["auction_date", "growing_zone"]).reset_index(drop=True)
    long_df["year"] = long_df["auction_date"].dt.year
    long_df["month"] = long_df["auction_date"].dt.month
    long_df["quarter"] = long_df["auction_date"].dt.quarter
    long_df["week"] = long_df["auction_date"].dt.isocalendar().week.astype(int)
    return long_df


def build_monthly_lstm_series(df: pd.DataFrame) -> pd.DataFrame:
    zone_monthly = df[
        ~df["growing_zone"].eq("Total")
        & df["quantity_kg"].notna()
        & df["avg_price_lkr"].notna()
    ][["auction_date", "growing_zone", "quantity_kg", "avg_price_lkr"]].copy()
    zone_monthly["source"] = "zone_row"

    total_rows = df[df["growing_zone"].eq("Total")].copy()

    if not total_rows.empty:
        total_monthly = total_rows[["auction_date", "growing_zone", "quantity_kg", "avg_price_lkr"]].copy()
        total_monthly["source"] = "total_row"
    else:
        total_monthly = pd.DataFrame()

    missing_total_months = sorted(set(df["auction_date"]) - set(total_monthly["auction_date"]))
    if missing_total_months:
        zone_rows = df[
            df["auction_date"].isin(missing_total_months)
            & ~df["growing_zone"].eq("Total")
            & df["quantity_kg"].notna()
            & df["avg_price_lkr"].notna()
        ].copy()

        fallback = (
            zone_rows.assign(weighted_price=zone_rows["quantity_kg"] * zone_rows["avg_price_lkr"])
            .groupby("auction_date", as_index=False)
            .agg(quantity_kg=("quantity_kg", "sum"), weighted_price=("weighted_price", "sum"))
        )
        fallback["avg_price_lkr"] = fallback["weighted_price"] / fallback["quantity_kg"]
        fallback = fallback.drop(columns=["weighted_price"])
        fallback["growing_zone"] = "Total"
        fallback["source"] = "weighted_zone_average"
        total_monthly = pd.concat([total_monthly, fallback], ignore_index=True)

    monthly = pd.concat([zone_monthly, total_monthly], ignore_index=True)
    monthly = monthly.sort_values(["growing_zone", "auction_date"]).drop_duplicates(
        ["growing_zone", "auction_date"],
        keep="first",
    )
    monthly = monthly.dropna(subset=["auction_date", "growing_zone", "avg_price_lkr"]).reset_index(drop=True)

    monthly["year"] = monthly["auction_date"].dt.year
    monthly["month"] = monthly["auction_date"].dt.month
    monthly["quarter"] = monthly["auction_date"].dt.quarter
    monthly["week"] = monthly["auction_date"].dt.isocalendar().week.astype(int)

    return monthly


def report_monthly_quality(monthly: pd.DataFrame) -> None:
    """Report gaps instead of interpolating across a train/test boundary."""
    required_missing = monthly[["auction_date", "growing_zone", "avg_price_lkr"]].isna().sum().to_dict()
    print(f"Missing required monthly values: {required_missing}")
    for zone, zone_df in monthly.groupby("growing_zone"):
        dates = pd.DatetimeIndex(zone_df["auction_date"].sort_values())
        expected = pd.date_range(dates.min(), dates.max(), freq="MS")
        missing_months = len(expected.difference(dates))
        if missing_months:
            print(f"{zone}: {missing_months} missing calendar month(s); retained as gaps to avoid imputation leakage.")


def main():
    print("Reading dataset...")
    raw_df = load_raw_dataset(INPUT_FILE)
    print("\nOriginal shape:")
    print(raw_df.shape)

    long_df = build_zone_long_format(raw_df)
    long_df["quantity_kg"] = clean_number(long_df["quantity_kg"])
    long_df["avg_price_lkr"] = clean_number(long_df["avg_price_lkr"])
    long_df = long_df.dropna(subset=["auction_date", "avg_price_lkr"])
    long_df = long_df.sort_values(["auction_date", "growing_zone"]).reset_index(drop=True)
    long_df["year"] = long_df["auction_date"].dt.year
    long_df["month"] = long_df["auction_date"].dt.month
    long_df["quarter"] = long_df["auction_date"].dt.quarter
    long_df["week"] = long_df["auction_date"].dt.isocalendar().week.astype(int)

    lstm_df = build_monthly_lstm_series(long_df)
    report_monthly_quality(lstm_df)

    train_parts = []
    test_parts = []
    for _, zone_df in lstm_df.groupby("growing_zone", sort=True):
        train_size = int(len(zone_df) * TRAIN_RATIO)
        train_parts.append(zone_df.iloc[:train_size].copy())
        test_parts.append(zone_df.iloc[train_size:].copy())

    train_df = pd.concat(train_parts, ignore_index=True)
    test_df = pd.concat(test_parts, ignore_index=True)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    long_df.to_csv(CLEAN_FILE, index=False)
    lstm_df.to_csv(MONTHLY_FILE, index=False)
    train_df.to_csv(TRAIN_FILE, index=False)
    test_df.to_csv(TEST_FILE, index=False)

    print("\nCleaning completed successfully!")
    print(f"Clean rows    : {len(long_df)}")
    print(f"LSTM rows     : {len(lstm_df)}")
    print(f"Train rows    : {len(train_df)}")
    print(f"Test rows     : {len(test_df)}")
    print(f"Zones         : {', '.join(sorted(lstm_df['growing_zone'].unique()))}")
    print(f"Train period  : {train_df['auction_date'].min().date()} to {train_df['auction_date'].max().date()}")
    print(f"Test period   : {test_df['auction_date'].min().date()} to {test_df['auction_date'].max().date()}")
    print(f"\nSaved to      : {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
