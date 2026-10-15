#!/usr/bin/env python3
"""Step 20: NASA POWER point daily climate data preparation (historical only).

Run from any working directory:
    python backend/app/components/Component01/src/m03_severity_climate/20_prepare_nasa_climate.py

No synthetic disease labels are read or generated. No climate-only disease-risk
prediction is made. Rolling aggregates are as-of the END of the indexed day.
"""
from __future__ import annotations

import argparse
import json
import re
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "data" / "raw" / "climate" / "nasa_power_daily.csv"
DEFAULT_PROCESSED = ROOT / "data" / "processed"
DEFAULT_REPORTS = ROOT / "outputs" / "reports"
FIELDS = [
    "ALLSKY_SFC_SW_DWN", "WS2M", "T2M", "T2M_MAX", "T2M_MIN",
    "RH2M", "PS", "PRECTOTCORR", "WSC",
]
REQUIRED = ["YEAR", "MO", "DY", *FIELDS]


def parse_nasa_power(path: Path) -> tuple[pd.DataFrame, dict]:
    if not path.is_file():
        raise FileNotFoundError(f"NASA climate file missing: {path}")
    with path.open("r", encoding="utf-8-sig") as handle:
        lines = handle.readlines()
    data_idx = next(
        (i for i, line in enumerate(lines)
         if re.match(r"^\s*YEAR\s*,\s*MO\s*,\s*DY\s*,", line, flags=re.I)),
        None,
    )
    if data_idx is None:
        raise ValueError("NASA data header YEAR,MO,DY,... was not found")
    meta_lines = [line.rstrip("\r\n") for line in lines[:data_idx]]
    df = pd.read_csv(StringIO("".join(lines[data_idx:])), skip_blank_lines=True)
    df.columns = [str(c).strip().upper() for c in df.columns]
    absent = [c for c in REQUIRED if c not in df.columns]
    if absent:
        raise ValueError(f"Missing required NASA columns: {absent}")
    if df.empty:
        raise ValueError("NASA climate file contains no data rows")

    for c in REQUIRED:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df[REQUIRED] = df[REQUIRED].replace(-999, np.nan)
    if df[["YEAR", "MO", "DY"]].isna().any().any():
        raise ValueError("Invalid or missing dates in YEAR/MO/DY; check source CSV")
    try:
        dates = pd.to_datetime({
            "year": df["YEAR"].astype(int),
            "month": df["MO"].astype(int),
            "day": df["DY"].astype(int),
        }, errors="raise")
    except Exception as err:
        raise ValueError(f"Invalid dates in NASA data: {err}") from err
    df.insert(0, "Date", dates)
    if df["Date"].duplicated().any():
        duplicates = df.loc[df["Date"].duplicated(), "Date"].dt.strftime("%Y-%m-%d").head(5).tolist()
        raise ValueError(f"Duplicate climate dates; refusing to proceed: {duplicates}")
    df = df.sort_values("Date").reset_index(drop=True)
    metadata = {"header": meta_lines}
    coordinates = next((line for line in meta_lines if "Location: latitude" in line), "")
    m = re.search(r"latitude\s+([-+]?\d+(?:\.\d+)?)\s+longitude\s+([-+]?\d+(?:\.\d+)?)", coordinates)
    if m:
        metadata["latitude"] = float(m.group(1))
        metadata["longitude"] = float(m.group(2))
    return df, metadata


def prepare_features(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    frame = raw[["Date", *FIELDS]].copy().set_index("Date").sort_index()
    start, end = frame.index.min(), frame.index.max()
    full_index = pd.date_range(start, end, freq="D", name="Date")
    missing_calendar_days = len(full_index) - len(frame)
    frame = frame.reindex(full_index)
    frame.insert(0, "Source_Row_Present", frame.index.isin(raw["Date"]).astype(int))

    # Hard quality warnings: retain original measurements, never silently clip values.
    issues = {}
    issues["humidity_outside_0_100"] = int(((frame.RH2M < 0) | (frame.RH2M > 100)).sum())
    issues["negative_rainfall"] = int((frame.PRECTOTCORR < 0).sum())
    issues["temp_max_below_min"] = int((frame.T2M_MAX < frame.T2M_MIN).sum())
    issues["negative_solar_irradiance"] = int((frame.ALLSKY_SFC_SW_DWN < 0).sum())

    frame["Year"] = frame.index.year
    frame["Month"] = frame.index.month
    frame["Day_Of_Year"] = frame.index.dayofyear
    frame["Month_Sin"] = np.sin(2 * np.pi * frame["Month"] / 12)
    frame["Month_Cos"] = np.cos(2 * np.pi * frame["Month"] / 12)
    frame["Temp_Range_C"] = frame.T2M_MAX - frame.T2M_MIN
    frame["Is_Rainy_Day"] = np.where(frame.PRECTOTCORR.isna(), np.nan, (frame.PRECTOTCORR > 1.0).astype(float))

    # IMPORTANT: '7D' etc include day t, hence are only known as of END OF DAY t.
    for n in (7, 14, 30):
        frame[f"T2M_Mean_{n}D"] = frame.T2M.rolling(n, min_periods=n).mean()
        frame[f"RH2M_Mean_{n}D"] = frame.RH2M.rolling(n, min_periods=n).mean()
        frame[f"Rainfall_Sum_{n}D"] = frame.PRECTOTCORR.rolling(n, min_periods=n).sum()
        frame[f"Solar_Mean_{n}D"] = frame.ALLSKY_SFC_SW_DWN.rolling(n, min_periods=n).mean()
    # Genuine prior-day values can support predictions at the beginning of a day.
    for col in ("T2M", "RH2M", "PRECTOTCORR"):
        frame[f"{col}_Lag_1D"] = frame[col].shift(1)
    frame["Daily_Climate_Complete"] = frame[FIELDS].notna().all(axis=1).astype(int)

    out = frame.reset_index()
    out["Date"] = out["Date"].dt.strftime("%Y-%m-%d")
    quality = {
        "source_rows": int(len(raw)),
        "calendar_rows": int(len(out)),
        "missing_calendar_days": int(missing_calendar_days),
        "start_date": str(start.date()),
        "end_date": str(end.date()),
        "missing_values_per_raw_variable": {k: int(v) for k, v in frame[FIELDS].isna().sum().items()},
        "incomplete_daily_records": int((out["Daily_Climate_Complete"] == 0).sum()),
        "plausibility_warnings": issues,
    }
    return out, quality


def build_weekly(daily: pd.DataFrame) -> pd.DataFrame:
    df = daily.copy()
    df["Date"] = pd.to_datetime(df["Date"])
    df["Week_Start"] = df["Date"] - pd.to_timedelta(df["Date"].dt.weekday, unit="D")
    weekly = df.groupby("Week_Start", as_index=False).agg(
        Calendar_Days=("Date", "size"),
        Complete_Days=("Daily_Climate_Complete", "sum"),
        T2M_Mean=("T2M", "mean"),
        RH2M_Mean=("RH2M", "mean"),
        PRECTOTCORR_Sum=("PRECTOTCORR", "sum"),
        Solar_Mean=("ALLSKY_SFC_SW_DWN", "mean"),
        WS2M_Mean=("WS2M", "mean"),
    )
    weekly["Complete_Week"] = ((weekly.Calendar_Days == 7) & (weekly.Complete_Days == 7)).astype(int)
    # A week with even one missing rainfall measurement has NO valid full-week rainfall sum.
    weekly.loc[weekly.Complete_Week != 1, [
        "T2M_Mean", "RH2M_Mean", "PRECTOTCORR_Sum", "Solar_Mean", "WS2M_Mean",
    ]] = np.nan
    weekly["Week_Start"] = weekly["Week_Start"].dt.strftime("%Y-%m-%d")
    return weekly


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--processed-dir", type=Path, default=DEFAULT_PROCESSED)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS)
    args = parser.parse_args()

    raw, source_metadata = parse_nasa_power(args.input)
    daily, quality = prepare_features(raw)
    weekly = build_weekly(daily)
    args.processed_dir.mkdir(parents=True, exist_ok=True)
    args.reports_dir.mkdir(parents=True, exist_ok=True)
    daily_out = args.processed_dir / "climate_daily_features.csv"
    weekly_out = args.processed_dir / "climate_weekly_summary.csv"
    summary_out = args.reports_dir / "step20_nasa_climate_quality.json"
    daily.to_csv(daily_out, index=False, na_rep="")
    weekly.to_csv(weekly_out, index=False, na_rep="")

    report = {
        "step": 20,
        "status": "HISTORICAL_CLIMATE_PREPROCESSED_NOT_DISEASE_MODEL",
        "source": "NASA POWER Point Daily",
        "source_file": str(args.input),
        "latitude": source_metadata.get("latitude"),
        "longitude": source_metadata.get("longitude"),
        "quality": quality,
        "weekly_complete_count": int(weekly["Complete_Week"].sum()),
        "weekly_incomplete_count": int((weekly["Complete_Week"] == 0).sum()),
        "feature_availability": "Rolling 7/14/30-day features include same-day observations, available end-of-day only. Lag_1D uses prior day.",
        "restrictions": [
            "One NASA POWER point; not automatically representative of all plantations or blocks.",
            "No observed disease labels are supplied; this script does not estimate disease risk.",
            "Do not interpret future-period weather or disease outcomes as measured or predicted by this script.",
            "Weekly aggregates marked incomplete must not be used as full-week observations.",
            "Reverify NASA location matches your target plantation before scientific use.",
        ],
        "artifacts": {"daily": str(daily_out), "weekly": str(weekly_out)},
    }
    with summary_out.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)

    print("=" * 76)
    print("STEP 20 - NASA POWER DAILY CLIMATE PREPARATION")
    print("=" * 76)
    print(f"Source rows: {quality['source_rows']} | Calendar rows: {quality['calendar_rows']}")
    print(f"Coverage: {quality['start_date']} to {quality['end_date']}")
    print(f"Missing calendar days: {quality['missing_calendar_days']}")
    print(f"Missing values: {quality['missing_values_per_raw_variable']}")
    print(f"Complete historical weeks: {report['weekly_complete_count']}")
    print(f"Source location: {report['latitude']}, {report['longitude']} (verify estate match)")
    print(f"Daily: {daily_out}")
    print(f"Weekly: {weekly_out}")
    print(f"Report: {summary_out}")
    print("PASS: preprocessing complete; no disease model was trained.")
    print("CAUTION: Rolling features are end-of-day; source location must be verified.")


if __name__ == "__main__":
    main()
