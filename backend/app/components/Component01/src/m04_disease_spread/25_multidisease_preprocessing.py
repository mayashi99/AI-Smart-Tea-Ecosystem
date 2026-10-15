"""Step 25: train-fitted, leakage-screened four-disease CSV preprocessing.

For a SIMULATED 16-block estate; NOT real-world-validated. Run from any cwd.
Input: data/synthetic/synthetic_block_records_multidisease.csv (Step 23).
Output: processed feature tables + TRAIN-fitted imputer/scaler artifact.
Never modifies source, never performs model selection or reports test performance.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

DISEASES = ["Brown Blight", "Grey Leaf", "Red Rust", "Red Spider Mite"]
SPLITS = ["train", "validation", "test"]
BASE_FEATURES = [
    "Observation_Available", "Inspected_Bushes", "Symptomatic_Bushes",
    "Sample_Incidence_Pct", "Latest_Observed_Incidence_Pct",
    "Days_Since_Last_Inspection", "T2M", "RH2M", "PRECTOTCORR",
    "ALLSKY_SFC_SW_DWN", "Humidity_Mean_7D", "Rainfall_Sum_7D",
    "Neighbor_Latest_Incidence_Mean_Pct", "Neighbor_Recent_Positive_Count",
]
STATIC_FEATURES = ["Grid_Row", "Grid_Column", "Relative_Vulnerability"]
CALENDAR_FEATURES = ["Day_Of_Year_Sin", "Day_Of_Year_Cos", "Weekday_Sin", "Weekday_Cos"]
NUMERIC_FEATURES = BASE_FEATURES + STATIC_FEATURES + CALENDAR_FEATURES
INSPECTION_FIELDS = ["Inspected_Bushes", "Symptomatic_Bushes", "Sample_Incidence_Pct"]
MISSING_FLAGS = [f"Missing_{name}" for name in INSPECTION_FIELDS]
DISEASE_ONEHOT = [f"Disease_{re.sub('[^a-z0-9]+', '_', name.lower()).strip('_')}" for name in DISEASES]
FEATURES = NUMERIC_FEATURES + MISSING_FLAGS + DISEASE_ONEHOT
META = ["Forecast_Origin_Date", "Estate_ID", "Block_ID", "Disease_Name", "Split"]
TARGETS = [f"Target_{kind}_Day_{h}" for h in range(1, 8)
           for kind in ("Disease_Active", "Incidence_Pct", "New_Onset_By")]


def require(ok: bool, msg: str) -> None:
    if not ok:
        raise ValueError(msg)


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def validate_and_prepare(raw: pd.DataFrame, blocks: pd.DataFrame) -> pd.DataFrame:
    required = META + BASE_FEATURES + TARGETS + ["Date", "Forecast_Horizon_Days", "All_7_Targets_Available"]
    required += [f"Target_Date_Day_{d}" for d in range(1, 8)]
    require(not (set(required) - set(raw.columns)),
            f"Missing input columns: {sorted(set(required) - set(raw.columns))}")
    require(set(["Block_ID", "Estate_ID"] + STATIC_FEATURES).issubset(blocks.columns),
            "Missing estate block metadata")
    require(len(blocks) == 16 and blocks.Block_ID.nunique() == 16, "Expected 16 distinct blocks")
    require(len(raw) > 0 and set(raw.Disease_Name.unique()) == set(DISEASES),
            "Expected four supported disease labels; do not include Healthy")
    require(set(raw.Split.unique()) == set(SPLITS + ["gap", "warmup", "inference_only"]),
            "Unexpected split values")
    require(not raw.duplicated(["Date", "Estate_ID", "Block_ID", "Disease_Name"]).any(),
            "Duplicate block/date/disease rows")
    require(raw.Block_ID.isin(blocks.Block_ID).all(), "Unknown block identifiers")
    require(raw.Forecast_Horizon_Days.eq(7).all(), "Expected 7-day forecast data")
    require(raw.groupby(["Date", "Block_ID"]).Disease_Name.nunique().eq(4).all(),
            "Every date/block must contain four diseases")
    selected = raw.loc[raw.Split.isin(SPLITS)].copy()
    require(len(selected) > 0, "No model-ready rows")
    require(selected.All_7_Targets_Available.eq(1).all(), "Incomplete 7-day labels")
    require(all((selected.Split == split).any() for split in SPLITS), "A modelling split is missing")

    selected["Forecast_Origin_Date"] = pd.to_datetime(selected.Forecast_Origin_Date, errors="raise")
    dates = pd.to_datetime(selected.Date, errors="raise")
    require((dates == selected.Forecast_Origin_Date).all(), "Date != forecast origin")
    for d in range(1, 8):
        date_col = f"Target_Date_Day_{d}"
        target_dt = pd.to_datetime(selected[date_col], errors="raise")
        require((target_dt == selected.Forecast_Origin_Date + pd.Timedelta(days=d)).all(),
                f"Incorrect forecast target date in {date_col}")
    for left, right in (("train", "validation"), ("validation", "test")):
        left_last = selected.loc[selected.Split.eq(left), "Forecast_Origin_Date"].max() + pd.Timedelta(days=7)
        right_first = selected.loc[selected.Split.eq(right), "Forecast_Origin_Date"].min()
        require(left_last < right_first, f"Future-target overlap between {left} and {right}")

    # Join only static block descriptors. No target or post-origin columns.
    meta = blocks[["Block_ID", "Estate_ID"] + STATIC_FEATURES].copy()
    require(not meta.duplicated("Block_ID").any(), "Duplicate block descriptors")
    selected = selected.merge(meta, on=["Block_ID", "Estate_ID"], how="left", validate="many_to_one")
    require(selected[STATIC_FEATURES].notna().all().all(), "Missing static block information")

    for col in BASE_FEATURES + STATIC_FEATURES:
        selected[col] = pd.to_numeric(selected[col], errors="raise")
        selected[col] = selected[col].replace([np.inf, -np.inf], np.nan)

    require(selected["Observation_Available"].isin([0, 1]).all(), "Invalid observation flag")
    for col in INSPECTION_FIELDS:
        # No officer inspection -> unknown measurement, not zero incidence.
        require(selected.loc[selected.Observation_Available.eq(0), col].isna().all(),
                f"Expected missing values when inspection unavailable: {col}")
        require(selected.loc[selected.Observation_Available.eq(1), col].notna().all(),
                f"Missing reported inspection measurement when inspection available: {col}")
    for col in ["Sample_Incidence_Pct", "Latest_Observed_Incidence_Pct", "Neighbor_Latest_Incidence_Mean_Pct"]:
        require(selected[col].dropna().between(0, 100).all(), f"Out-of-range percentage: {col}")
    require(selected["Inspected_Bushes"].dropna().gt(0).all(), "Inspected_Bushes <= 0")
    require((selected["Symptomatic_Bushes"].fillna(0) <= selected["Inspected_Bushes"].fillna(0)).all(),
            "Symptomatic_Bushes > Inspected_Bushes")

    dayofyear = selected.Forecast_Origin_Date.dt.dayofyear
    weekday = selected.Forecast_Origin_Date.dt.dayofweek
    selected["Day_Of_Year_Sin"] = np.sin(2 * np.pi * dayofyear / 365.25)
    selected["Day_Of_Year_Cos"] = np.cos(2 * np.pi * dayofyear / 365.25)
    selected["Weekday_Sin"] = np.sin(2 * np.pi * weekday / 7.0)
    selected["Weekday_Cos"] = np.cos(2 * np.pi * weekday / 7.0)

    for col in TARGETS:
        selected[col] = pd.to_numeric(selected[col], errors="raise")
        require(selected[col].notna().all(), f"Missing eligible target values: {col}")
        if "Incidence" in col:
            require(selected[col].between(0, 100).all(), f"Invalid incidence target: {col}")
        else:
            require(selected[col].isin([0, 1]).all(), f"Invalid binary target: {col}")

    require(not any(x.startswith("Target_") for x in FEATURES), "Target leakage into predictor whitelist")
    require(not set(FEATURES).intersection({"Split", "Date", "All_7_Targets_Available"}),
            "Forbidden feature present")
    selected["Forecast_Origin_Date"] = selected.Forecast_Origin_Date.dt.strftime("%Y-%m-%d")
    return selected


def fit_train_preprocessor(train: pd.DataFrame) -> dict:
    require(not train.empty and train.Split.eq("train").all(), "Fit preprocessing on TRAIN ONLY")
    # Missing flags are fitted from data availability, not from targets.
    raw_train = train[NUMERIC_FEATURES].astype(float).replace([np.inf, -np.inf], np.nan)
    require(raw_train.notna().any(axis=0).all(), "At least one numeric feature is entirely missing in train")
    imputer = SimpleImputer(strategy="median", keep_empty_features=True)
    imputer.fit(raw_train)
    prep = {"imputer": imputer, "feature_columns": FEATURES,
            "numeric_features": NUMERIC_FEATURES, "disease_names": DISEASES,
            "missing_flags": MISSING_FLAGS, "disease_onehot": DISEASE_ONEHOT,
            "training_only_fit": True,
            "inference_semantics": "end_of_day; no future climate or target columns allowed"}
    # Scaler for sequence models is fitted on TRAIN ONLY after median fill/encoding.
    train_features = transform_features(train, prep)
    prep["scaler"] = StandardScaler().fit(train_features[FEATURES].to_numpy(dtype=float))
    return prep


def transform_features(frame: pd.DataFrame, prep: dict) -> pd.DataFrame:
    """Reusable for inference: use saved TRAIN-fitted imputer and fixed disease order."""
    numeric = prep["numeric_features"]
    require(set(numeric + ["Disease_Name"]).issubset(frame.columns), "Missing inference features")
    require(frame.Disease_Name.isin(prep["disease_names"]).all(), "Unsupported disease at inference")
    nums = frame[numeric].copy()
    for col in numeric:
        nums[col] = pd.to_numeric(nums[col], errors="raise")
    nums = nums.replace([np.inf, -np.inf], np.nan)
    arr = prep["imputer"].transform(nums)
    out = pd.DataFrame(arr, columns=numeric, index=frame.index)
    for field, name in zip(INSPECTION_FIELDS, prep["missing_flags"]):
        out[name] = nums[field].isna().astype(int)
    for disease, name in zip(prep["disease_names"], prep["disease_onehot"]):
        out[name] = frame.Disease_Name.eq(disease).astype(int)
    require(out[prep["feature_columns"]].notna().all().all(), "Non-finite transformed features")
    require(np.isfinite(out[prep["feature_columns"]].to_numpy(dtype=float)).all(), "Non-finite values")
    return out[prep["feature_columns"]]


def build(component_root: Path) -> dict:
    root = component_root.resolve()
    source = root / "data" / "synthetic" / "synthetic_block_records_multidisease.csv"
    blockfile = root / "data" / "synthetic" / "estate_blocks.csv"
    processed = root / "data" / "processed"
    reports = root / "outputs" / "reports"
    configs = root / "configs"
    for folder in [processed, reports, configs]:
        folder.mkdir(parents=True, exist_ok=True)
    require(source.is_file() and blockfile.is_file(), "Step 23 files missing: run Step 23 first")
    raw = pd.read_csv(source, encoding="utf-8-sig", low_memory=False)
    blocks = pd.read_csv(blockfile, encoding="utf-8-sig")
    selected = validate_and_prepare(raw, blocks)
    train = selected.loc[selected.Split.eq("train")]
    prep = fit_train_preprocessor(train)

    split_counts = {}
    missing_before = {}
    for split in SPLITS:
        data = selected.loc[selected.Split.eq(split)].copy()
        matrix = transform_features(data, prep)
        output = pd.concat([data[META].reset_index(drop=True),
                            matrix.reset_index(drop=True),
                            data[TARGETS].reset_index(drop=True)], axis=1)
        output = output.sort_values(["Forecast_Origin_Date", "Disease_Name", "Block_ID"])
        require(not output.duplicated(["Forecast_Origin_Date", "Estate_ID", "Block_ID", "Disease_Name"]).any(),
                "Duplicate transformed keys")
        require(output[FEATURES].notna().all().all(), "Remaining null predictors")
        name = processed / f"multidisease_preprocessed_{split}.csv"
        output.to_csv(name, index=False)
        split_counts[split] = len(output)
        missing_before[split] = {col: int(data[col].isna().sum()) for col in INSPECTION_FIELDS}

    require(split_counts == {"train": 45440, "validation": 22464, "test": 13248},
            f"Unexpected original simulation split sizes: {split_counts}")
    artifact = processed / "multidisease_train_fitted_preprocessor.joblib"
    joblib.dump(prep, artifact)
    # Artifact is an untrusted-code vector if sourced from strangers; only load from this project.
    check = joblib.load(artifact)
    check_x = transform_features(train.head(4), check)
    require(check_x.shape == (4, len(FEATURES)), "Saved preprocessor could not be reloaded")
    contract = {
        "schema_version": "step25-v1", "scope": "Four-disease, 16-block SYNTHETIC demo",
        "diseases": DISEASES, "input_feature_columns": FEATURES,
        "base_numeric_features": NUMERIC_FEATURES,
        "target_columns": TARGETS, "metadata_columns": META,
        "target_semantics": "Day 1 through Day 7 future targets are labels ONLY",
        "fit_split": "train_only", "imputation": "median train only; missing inspection flags retained",
        "scaling": "StandardScaler saved and fitted train only; CSVs are unscaled, imputed for tree models",
        "inference": "Load multidisease_train_fitted_preprocessor.joblib and use transform_features."
                     " Every climate/inspection observation must be known by END OF ORIGIN DAY.",
        "feature_engineering_next": "Step 26 adds leakage-safe past-only lags; refit preprocessing on any newly engineered features",
        "prohibited_features": "Target_*, future climate, future officer reports, Split, target availability",
        "provenance": "SIMULATED DISEASES AND OFFICER OBSERVATIONS; single-point NASA history; site mismatch unresolved",
        "external_validation": False,
    }
    save_json(processed / "multidisease_preprocessing_contract.json", contract)
    report = {
        "status": "PASS_SIMULATION_ONLY", "source_rows": len(raw),
        "labelled_rows": int(sum(split_counts.values())), "split_counts": split_counts,
        "unique_blocks": int(selected.Block_ID.nunique()),
        "diseases": DISEASES, "feature_count": len(FEATURES), "target_count": len(TARGETS),
        "missing_inspection_before_train_fitted_imputation": missing_before,
        "preprocessor_joblib": str(artifact.relative_to(root)).replace("\\", "/"),
        "fit_split": "train_only", "test_target_metrics_computed": False,
        "warning": "Simulated multi-disease labels; not field validated. Test rows transformed only, not used for fitting.",
    }
    save_json(reports / "step25_multidisease_preprocessing_summary.json", report)
    print("=" * 77)
    print("STEP 25 - FOUR-DISEASE TRAIN-FITTED PREPROCESSING (SIMULATION ONLY)")
    print("=" * 77)
    print(f"Source rows: {len(raw)} | Labelled model rows: {sum(split_counts.values())}")
    print(f"Split counts: {split_counts}")
    print(f"Diseases: {DISEASES}")
    print(f"Predictors: {len(FEATURES)} | Targets: {len(TARGETS)}")
    print("Inspection missingness before TRAIN-ONLY imputation:", missing_before)
    print(f"Preprocessor: {artifact}")
    print(f"Contract: {processed / 'multidisease_preprocessing_contract.json'}")
    print(f"Report: {reports / 'step25_multidisease_preprocessing_summary.json'}")
    print("PASS: training-fitted preprocessing; no model training, test-based tuning or test metrics.")
    print("CAUTION: Training data and labels are SIMULATED; not real field-validation.")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    build(args.component_root)
