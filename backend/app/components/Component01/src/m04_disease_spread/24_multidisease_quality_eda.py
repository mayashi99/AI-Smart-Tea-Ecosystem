"""Step 24 — Data quality and EDA for the four-disease SYNTHETIC estate prototype.

No training, random split, imputation, normalization, source modification, or
clinical/agronomic validation is performed here. This is a read-only input audit.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

DISEASES = ["Brown Blight", "Grey Leaf", "Red Rust", "Red Spider Mite"]
SPLITS = ["warmup", "train", "gap", "validation", "inference_only", "test"]
MODEL_SPLITS = ["train", "validation", "test"]
BINARY_TARGETS = ("Disease_Active", "New_Onset_By")
TARGET_TYPES = ("Disease_Active", "Incidence_Pct", "New_Onset_By")
OFFICER_FEATURES = ["Inspected_Bushes", "Symptomatic_Bushes", "Sample_Incidence_Pct"]
OBSERVED_FEATURES = ["Observation_Available", "Latest_Observed_Incidence_Pct", "Days_Since_Last_Inspection",
                     "Neighbor_Latest_Incidence_Mean_Pct", "Neighbor_Recent_Positive_Count"]
CLIMATE_FEATURES = ["T2M", "RH2M", "PRECTOTCORR", "ALLSKY_SFC_SW_DWN",
                    "Humidity_Mean_7D", "Rainfall_Sum_7D"]
KEY = ["Date", "Estate_ID", "Block_ID", "Disease_Name"]


def check(ok: bool, message: str):
    if not ok:
        raise ValueError(message)


def ensure_dirs(root: Path):
    reports = root / "outputs" / "reports" / "multidisease_step24"
    figures = root / "outputs" / "figures" / "multidisease_step24"
    reports.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    return reports, figures


def run(root: Path) -> dict:
    root = root.resolve()
    input_file = root / "data" / "synthetic" / "synthetic_block_records_multidisease.csv"
    check(input_file.is_file(), f"Missing Step 23 output: {input_file}")
    blocks_file = root / "data" / "synthetic" / "estate_blocks.csv"
    edges_file = root / "data" / "synthetic" / "block_adjacency.csv"
    check(blocks_file.is_file() and edges_file.is_file(), "Missing estate blocks or adjacency CSV")
    df = pd.read_csv(input_file, low_memory=False)
    blocks = pd.read_csv(blocks_file)
    edges = pd.read_csv(edges_file)
    targets = [f"Target_{name}_Day_{day}" for day in range(1, 8) for name in TARGET_TYPES]
    target_dates = [f"Target_Date_Day_{day}" for day in range(1, 8)]
    expected = KEY + ["Forecast_Origin_Date", "Split", "Forecast_Horizon_Days",
                      "All_7_Targets_Available"] + OFFICER_FEATURES + OBSERVED_FEATURES + CLIMATE_FEATURES + targets + target_dates
    check(set(expected).issubset(df.columns), f"Missing required columns: {sorted(set(expected)-set(df.columns))}")
    check(len(df) > 0, "CSV empty")
    check(set(df.Disease_Name.unique()) == set(DISEASES), "Must have four expected disease labels")
    check(not df.duplicated(KEY).any(), "Repeated disease/block/date row found")
    check(set(df.Split.astype(str).unique()) <= set(SPLITS), "Unknown split value")
    check(df.Forecast_Horizon_Days.eq(7).all(), "Non-7-day forecast record found")
    check(blocks.Block_ID.nunique() == 16 and df.Block_ID.nunique() == 16, "Expected 16 unique estate blocks")
    check(len(edges) == 48 and set(edges.Source_Block).issubset(blocks.Block_ID) and
          set(edges.Target_Block).issubset(blocks.Block_ID), "Graph metadata invalid")
    check(set(df.Block_ID.unique()) == set(blocks.Block_ID.unique()), "Source blocks differ from metadata")
    check(df.Estate_ID.nunique() == 1, "Only one simulated estate expected")

    origin = pd.to_datetime(df.Forecast_Origin_Date, errors="coerce")
    dates = pd.to_datetime(df.Date, errors="coerce")
    check(origin.notna().all() and dates.notna().all(), "Invalid origin/date")
    check((origin == dates).all(), "Date != Forecast_Origin_Date")
    unique_dates = pd.DatetimeIndex(sorted(dates.unique()))
    check(((unique_dates[1:] - unique_dates[:-1]) == pd.Timedelta(days=1)).all(), "Non-consecutive date series")
    daily_counts = df.groupby("Date", sort=False).size()
    check(daily_counts.eq(64).all(), "Expected 16 blocks x 4 diseases on every date")
    check(len(df) == len(unique_dates) * 64, "Missing daily records")
    check(df.groupby("Date").Split.nunique().eq(1).all(), "Split should be common across diseases on each date")
    labelled = df.Split.isin(MODEL_SPLITS)
    check(df.loc[labelled, "All_7_Targets_Available"].eq(1).all(), "Incomplete labelled training rows")
    check(df.loc[labelled, targets].notna().all().all(), "Null target in train/validation/test")
    check(df.loc[labelled, target_dates].notna().all().all(), "Missing target date on modelling split")
    for day in range(1, 8):
        target_dt = pd.to_datetime(df[f"Target_Date_Day_{day}"], errors="coerce")
        check((target_dt.loc[labelled] == origin.loc[labelled] + pd.Timedelta(days=day)).all(),
              f"Target date misalignment horizon {day}")
        for name in BINARY_TARGETS:
            target_col = f"Target_{name}_Day_{day}"
            x = pd.to_numeric(df.loc[labelled, target_col], errors="coerce")
            check(x.isin((0, 1)).all(), f"Non-binary target {target_col}")
        incidence = pd.to_numeric(df.loc[labelled, f"Target_Incidence_Pct_Day_{day}"], errors="coerce")
        check(incidence.between(0, 100).all(), f"Incidence not 0..100 at horizon {day}")

    boundary = {}
    for prev, cur in (("train", "validation"), ("validation", "test")):
        p = origin[df.Split.eq(prev)]
        q = origin[df.Split.eq(cur)]
        check(len(p)>0 and len(q)>0, f"Missing modelling split: {prev}/{cur}")
        last_future = p.max() + pd.Timedelta(days=7)
        first_new_origin = q.min()
        check(last_future < first_new_origin,
              f"Leakage risk: {prev} last target {last_future.date()} >= {cur} first origin {first_new_origin.date()}")
        boundary[f"{prev}_to_{cur}"] = {"last_previous_target": str(last_future.date()),
                                       "first_next_origin": str(first_new_origin.date()),
                                       "gap_days": int((first_new_origin-last_future).days)}
    check(set(df.Observation_Source.dropna().unique()) <= {"SYNTHETIC_FIELD_SIMULATION", "SYNTHETIC_MULTIDISEASE_SCENARIO_V1"},
          "Unexpected observation provenance; investigate before using outputs")
    check(df["Observation_Source"].notna().all(), "Missing observation provenance")
    missing_expected = {}
    obs = pd.to_numeric(df.Observation_Available, errors="coerce")
    check(obs.isin((0, 1)).all(), "Observation_Available should be binary")
    missing_officer_when_seen = 0
    for col in OFFICER_FEATURES:
        x = pd.to_numeric(df[col], errors="coerce")
        bad = int((obs.eq(1) & x.isna()).sum())
        missing_officer_when_seen += bad
        missing_expected[col] = {"missing_total": int(x.isna().sum()),
                                 "missing_when_no_inspection": int((obs.eq(0) & x.isna()).sum()),
                                 "missing_when_inspected": bad}
    check(missing_officer_when_seen == 0, "Missing inspection data when inspection marked available")
    check(df[CLIMATE_FEATURES].notna().all().all(), "Missing climate features")
    check(df["Latest_Observed_Incidence_Pct"].between(0, 100).all(), "Historical observed incidence out of range")
    check(df["Neighbor_Latest_Incidence_Mean_Pct"].between(0, 100).all(), "Neighbor incidence out of range")
    check(df.loc[obs.eq(1),"Symptomatic_Bushes"].le(df.loc[obs.eq(1),"Inspected_Bushes"]).all(),
          "Observed symptomatic count exceeds inspection count")

    reports, figures = ensure_dirs(root)
    split_table = df.groupby(["Disease_Name", "Split"], observed=True).size().unstack(fill_value=0)
    split_table = split_table.reindex(index=DISEASES, columns=SPLITS, fill_value=0)
    split_table.to_csv(reports/"disease_split_counts.csv")
    missing_df = pd.DataFrame([{ "column": col, "missing": int(df[col].isna().sum()),
                               "missing_pct": round(float(df[col].isna().mean()*100),3),
                               "notes": "Expected when no inspection" if col in OFFICER_FEATURES else ""}
                              for col in df.columns])
    missing_df.to_csv(reports/"column_missingness.csv", index=False)

    sample_rows = []
    # Keep held-out TEST outcomes out of descriptive EDA/model-selection reports.
    labelled_df = df.loc[df.Split.isin(["train", "validation"])].copy()
    for disease in DISEASES:
        for split in ("train", "validation"):
            subset = labelled_df[(labelled_df.Disease_Name==disease) & (labelled_df.Split==split)]
            for day in range(1,8):
                sample_rows.append({"disease": disease, "split": split, "horizon_days": day,
                                    "n_rows": len(subset),
                                    "active_prevalence": float(subset[f"Target_Disease_Active_Day_{day}"].mean()),
                                    "new_onset_rate": float(subset[f"Target_New_Onset_By_Day_{day}"].mean()),
                                    "mean_incidence_pct": float(subset[f"Target_Incidence_Pct_Day_{day}"].mean())})
    stats = pd.DataFrame(sample_rows)
    stats.to_csv(reports / "disease_target_distribution_by_horizon.csv", index=False)
    distribution = (df.loc[df.Split.eq("train")].groupby("Disease_Name")[CLIMATE_FEATURES+OBSERVED_FEATURES].agg(["mean","std","min","max"]))
    distribution.columns = [f"{a}_{b}" for a,b in distribution.columns]
    distribution.to_csv(reports / "feature_distribution_by_disease.csv")
    train_only = labelled_df.loc[labelled_df.Split.eq("train")].copy()
    monthly = train_only.assign(Year_Month=pd.to_datetime(train_only.Date).dt.to_period('M').astype(str)).groupby(
        ["Year_Month","Disease_Name"], as_index=False).agg(
            Active_Day_1=("Target_Disease_Active_Day_1","mean"),
            Mean_Incidence_Day_1=("Target_Incidence_Pct_Day_1","mean"),
            Records=("Block_ID","size"))
    monthly.to_csv(reports / "monthly_disease_trends.csv", index=False)

    fig, ax = plt.subplots(figsize=(9,5))
    for disease in DISEASES:
        z = stats[(stats.disease==disease) & (stats.split=="train")]
        ax.plot(z.horizon_days, z.active_prevalence, marker='o', label=disease)
    ax.set(title="Synthetic train-period disease activity by horizon", xlabel="Days ahead", ylabel="Active fraction")
    ax.set_ylim(bottom=0); ax.legend(fontsize=9); ax.grid(alpha=.25)
    fig.tight_layout(); fig.savefig(figures/"training_disease_activity_by_horizon.png",dpi=140); plt.close(fig)

    fig, ax = plt.subplots(figsize=(9,5))
    monthly_pivot = monthly.pivot(index="Year_Month",columns="Disease_Name",values="Active_Day_1")
    for disease in DISEASES:
        ax.plot(range(len(monthly_pivot)), monthly_pivot[disease], label=disease)
    tick = np.linspace(0,len(monthly_pivot)-1,min(8,len(monthly_pivot)),dtype=int)
    ax.set_xticks(tick, [monthly_pivot.index[i] for i in tick], rotation=30)
    ax.set(title="Simulated day-1 disease activity over time", xlabel="Month",ylabel="Active fraction")
    ax.set_ylim(bottom=0); ax.legend(fontsize=9); ax.grid(alpha=.25)
    fig.tight_layout(); fig.savefig(figures/"monthly_synthetic_disease_activity.png",dpi=140); plt.close(fig)

    report = {
        "status": "PASS_SIMULATION_ONLY", "rows": int(len(df)),
        "unique_dates":int(len(unique_dates)), "first_date":str(unique_dates[0].date()),
        "last_date":str(unique_dates[-1].date()), "blocks":int(blocks.Block_ID.nunique()),
        "diseases":DISEASES,"split_counts":{str(k):int(v) for k,v in df.Split.value_counts().items()},
        "duplicate_disease_date_block_keys": 0,
        "forecast_date_checks":"PASS_all_7_horizons", "modelling_targets_complete":True,
        "temporal_boundaries":boundary,"inspection_missingness":missing_expected,
        "source_provenance":df.groupby(["Disease_Name","Observation_Source"]).size().to_dict(),
        "caution":["SIMULATION ONLY; not verified multi-disease agricultural data",
                  "Historical NASA POWER location 6.7789, 79.9301 has not been verified for intended estate",
                  "Climate and inspection data are end-of-day: do not use to make same-day morning forecasts",
                  "Correlated/synthetic outcomes can produce misleadingly high validation metrics",
                  "No imputation, feature selection, scaling, model fitting or test-based tuning performed",
                  "Held-out test target outcomes are checked only for integrity, never summarized in EDA reports",
                  "Future target columns Target_* must NEVER be used as input features"],
        "next_step":"25_multidisease_preprocessing: whitelist features, train-only preprocessing, retain test untouched"
    }
    report["source_provenance"] = [{"disease": k[0],"source":k[1],"rows":int(v)}
                                   for k,v in df.groupby(["Disease_Name","Observation_Source"]).size().items()]
    (reports / "step24_multidisease_quality_summary.json").write_text(
        json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    print("="*77)
    print("STEP 24 - MULTI-DISEASE DATA QUALITY + EDA - SYNTHETIC ONLY")
    print("="*77)
    print(f"Rows: {len(df)} | Dates: {len(unique_dates)} | Blocks: {blocks.Block_ID.nunique()} | Diseases: {len(DISEASES)}")
    print(f"Split counts: {report['split_counts']}")
    print("Duplicate keys: 0 | Target alignment: PASS | Temporal split isolation: PASS")
    print("Officer-feature missingness (expected uninspected):", {k:v['missing_total'] for k,v in missing_expected.items()})
    print("Day-1 activity prevalence (train):")
    for disease in DISEASES:
        val = stats[(stats.disease==disease)&(stats.split=="train")&(stats.horizon_days==1)].active_prevalence.iloc[0]
        print(f"  {disease:18} : {val:.3f}")
    print("Reports:", reports)
    print("Figures:", figures)
    print("PASS: Step 24 quality + EDA completed. No input data modified or models trained.")
    print("WARNING: All spread results are simulation-based; actual estate performance unknown.")
    return report


def main():
    parser=argparse.ArgumentParser(description="Read-only Step24 multi-disease synthetic data quality & EDA")
    parser.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[2],
                        help="Component01 project root (default: deduced from file location)")
    args=parser.parse_args()
    run(args.root)

if __name__ == '__main__':
    main()
