"""Step 26: leakage-controlled history features for simulated four-disease spread.

Uses current/prior observations ONLY; all new lags and rolling aggregations are
strictly earlier than the forecast-origin day (shift(1)). Features computed on
complete original date history, so temporal split gaps are preserved as history,
but training/validation/test labels are NEVER read to build features.

Requires successful Step 23 + Step 25. The five-class CNN work is unrelated.
All estate and disease observations here are SIMULATED, not field validated.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

KEYS = ["Forecast_Origin_Date", "Estate_ID", "Block_ID", "Disease_Name"]
SPLITS = ("train", "validation", "test")
LAG_SOURCES = (
    "Latest_Observed_Incidence_Pct",
    "Neighbor_Latest_Incidence_Mean_Pct",
    "T2M",
    "RH2M",
    "PRECTOTCORR",
)
ROLL_SOURCES = (
    ("Latest_Observed_Incidence_Pct", "mean"),
    ("Neighbor_Latest_Incidence_Mean_Pct", "mean"),
    ("RH2M", "mean"),
    ("PRECTOTCORR", "sum"),
    ("Observation_Available", "sum"),
)
LAG_DAYS = (1, 3, 7)
WINDOW_DAYS = 7


def check(condition: bool, msg: str) -> None:
    if not condition:
        raise ValueError(msg)


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def expected_lag_features() -> list[str]:
    names = [f"Past_{c}_Lag{days}D" for c in LAG_SOURCES for days in LAG_DAYS]
    names += [f"Past_{c}_Rolling{WINDOW_DAYS}D_{func}" for c, func in ROLL_SOURCES]
    return names


def historical_features(raw: pd.DataFrame) -> pd.DataFrame:
    """Raw must be exclusively identifier + origin-observable columns.

    No future-target field is accepted, even when callers accidentally supply
    the entire forecasting CSV. This makes leakage harder to introduce.
    """
    required = set(KEYS + list(LAG_SOURCES) + ["Observation_Available", "Split"])
    check(required.issubset(raw.columns), f"Missing columns: {sorted(required - set(raw.columns))}")
    check(not any(c.startswith("Target_") for c in raw.columns),
          "Target columns supplied to historical feature builder; use input whitelist")
    frame = raw.copy()
    frame["Forecast_Origin_Date"] = pd.to_datetime(frame["Forecast_Origin_Date"], errors="raise")
    check(not frame.duplicated(KEYS).any(), "Duplicate date/estate/block/disease key")
    check(set(frame.Split.unique()) == {
        "train", "validation", "test", "warmup", "gap", "inference_only"
    }, "Expected original chronology with warmup, gap and inference-only rows")
    check(set(frame.Disease_Name.unique()) == {
        "Brown Blight", "Grey Leaf", "Red Rust", "Red Spider Mite"
    }, "Unexpected disease scope")
    check(frame.Block_ID.nunique() == 16, "Expected the 16 simulated estate blocks")
    for col in list(LAG_SOURCES) + ["Observation_Available"]:
        frame[col] = pd.to_numeric(frame[col], errors="raise")
        check(np.isfinite(frame[col].dropna().to_numpy(dtype=float)).all(), f"Nonfinite {col}")
    check(frame.Observation_Available.isin([0, 1]).all(), "Invalid observation flag")

    group_keys = ["Estate_ID", "Block_ID", "Disease_Name"]
    frame = frame.sort_values(group_keys + ["Forecast_Origin_Date"]).reset_index(drop=True)
    check((frame["Forecast_Origin_Date"].diff().where(
        frame[group_keys].eq(frame[group_keys].shift()).all(axis=1)
    ).dropna() == pd.Timedelta(days=1)).all(), "Missing date(s) in a block/disease history")

    g = frame.groupby(group_keys, sort=False, observed=True)
    for col in LAG_SOURCES:
        for days in LAG_DAYS:
            frame[f"Past_{col}_Lag{days}D"] = g[col].shift(days)
    for col, func in ROLL_SOURCES:
        new_col = f"Past_{col}_Rolling{WINDOW_DAYS}D_{func}"
        frame[new_col] = g[col].transform(
            lambda x: getattr(x.shift(1).rolling(WINDOW_DAYS, min_periods=1), func)()
        )

    features = expected_lag_features()
    check(not any(name.startswith("Target_") for name in features), "Future label leakage")
    frame["Forecast_Origin_Date"] = frame.Forecast_Origin_Date.dt.strftime("%Y-%m-%d")
    return frame[KEYS + ["Split"] + features]


def create(root: Path) -> dict:
    root = root.resolve()
    rawfile = root / "data" / "synthetic" / "synthetic_block_records_multidisease.csv"
    process_dir = root / "data" / "processed"
    report_dir = root / "outputs" / "reports"
    contract_file = process_dir / "multidisease_preprocessing_contract.json"
    preprocessor_file = process_dir / "multidisease_train_fitted_preprocessor.joblib"
    check(rawfile.is_file() and contract_file.is_file() and preprocessor_file.is_file(),
          "Steps 23 and 25 must run successfully before Step 26")
    contract25 = json.loads(contract_file.read_text(encoding="utf-8"))
    base_cols = contract25["input_feature_columns"]
    targets = contract25["target_columns"]
    check(len(base_cols) == 28 and len(targets) == 21, "Unexpected Step 25 contract")
    check(not set(base_cols).intersection(targets), "Target leakage in Step 25")
    old_prep = joblib.load(preprocessor_file)  # load ONLY local, trusted project-generated artifacts
    check(old_prep["training_only_fit"] is True, "Step 25 must be train-fitted")
    check(old_prep["feature_columns"] == base_cols, "Step 25 preprocessor/contract mismatch")

    # Critical: selectively read origin-day observables; NEVER read Target_* labels here.
    allowed = list(dict.fromkeys(KEYS + ["Split", "Observation_Available"] + list(LAG_SOURCES)))
    raw = pd.read_csv(rawfile, usecols=allowed, encoding="utf-8-sig", low_memory=False)
    history = historical_features(raw)
    new_cols = expected_lag_features()
    check(len(new_cols) == 20, "Expected 20 historical features")
    check(not history.duplicated(KEYS).any(), "Duplicate history key")
    full_features = base_cols + new_cols
    check(len(full_features) == len(set(full_features)), "Repeated predictor column names")

    split_frames = {}
    missing_by_split = {}
    for split in SPLITS:
        path = process_dir / f"multidisease_preprocessed_{split}.csv"
        check(path.is_file(), f"Missing Step 25 transformed table {path}")
        frame = pd.read_csv(path, low_memory=False)
        check(set(KEYS + ["Split"] + base_cols + targets).issubset(frame.columns),
              f"Bad Step 25 feature table: {split}")
        check(frame.Split.eq(split).all(), f"Incorrect split tag: {split}")
        check(not frame.duplicated(KEYS).any(), f"Duplicate Step 25 row keys: {split}")
        joined = frame.merge(history, on=KEYS, how="left", validate="one_to_one",
                             suffixes=("", "_history"), indicator=True)
        check(joined._merge.eq("both").all(), f"Unmatched historical rows for {split}")
        check(joined["Split_history"].eq(split).all(), "Split changed during merge")
        joined = joined.drop(columns=["Split_history", "_merge"])
        check(len(joined) == len(frame), "Merge changed row count")
        check(joined[targets].notna().all().all(), f"Missing labels in {split} table")
        check(joined[base_cols].notna().all().all(), f"Step 25 features have missing values: {split}")
        for col in new_cols:
            joined[col] = pd.to_numeric(joined[col], errors="raise")
            joined[col] = joined[col].replace([np.inf, -np.inf], np.nan)
        missing_by_split[split] = {col: int(joined[col].isna().sum()) for col in new_cols}
        split_frames[split] = joined

    train = split_frames["train"]
    imputer = SimpleImputer(strategy="median", keep_empty_features=True)
    check(train[new_cols].notna().any(axis=0).all(), "Historical feature entirely missing in train")
    imputer.fit(train[new_cols])  # TRAIN ONLY
    for split in SPLITS:
        src = split_frames[split]
        lagged = imputer.transform(src[new_cols])
        check(np.isfinite(lagged).all(), f"Nonfinite imputed history for {split}")
        src.loc[:, new_cols] = lagged
        check(src[full_features].notna().all().all(), f"Missing predictor for {split}")
        check(np.isfinite(src[full_features].to_numpy(dtype=float)).all(),
              f"Nonfinite full feature matrix for {split}")
        ordered_cols = KEYS + ["Split"] + full_features + targets
        src = src[ordered_cols].sort_values(
            ["Forecast_Origin_Date", "Disease_Name", "Block_ID"]
        ).reset_index(drop=True)
        split_frames[split] = src

    # Fit new scaler for the complete 48-column input schema: NEVER reuse old scaler.
    full_scaler = StandardScaler().fit(split_frames["train"][full_features].to_numpy(dtype=float))
    check(full_scaler.n_features_in_ == len(full_features), "Scaler feature dimension mismatch")
    prep26 = {
        "schema_version": "step26-v1",
        "historical_columns": new_cols,
        "base_feature_columns": base_cols,
        "feature_columns": full_features,
        "target_columns": targets,
        "lag_imputer": imputer,
        "full_feature_scaler_train_only": full_scaler,
        "source_step25_preprocessor": "multidisease_train_fitted_preprocessor.joblib",
        "training_only_fit": True,
        "historical_features": "shift(1) before rolling: prior days only",
        "provenance": "SIMULATED_ESTATE_4_DISEASES",
    }
    artifact = process_dir / "multidisease_step26_feature_pipeline.joblib"
    joblib.dump(prep26, artifact)
    loaded = joblib.load(artifact)
    check(loaded["feature_columns"] == full_features, "Failed to reload saved feature contract")
    check(loaded["full_feature_scaler_train_only"].n_features_in_ == 48,
          "Saved scaler has incorrect dimensionality")

    counts = {}
    for split, table in split_frames.items():
        destination = process_dir / f"multidisease_features_{split}.csv"
        table.to_csv(destination, index=False)
        counts[split] = len(table)
    check(counts == {"train": 45440, "validation": 22464, "test": 13248},
          f"Unexpected historical demo split sizes: {counts}")
    final_contract = {
        "schema_version": "step26-v1",
        "scope": "four disease; simulated 16-block estate; end-of-day forecast origin",
        "disease_names": contract25["diseases"],
        "metadata_columns": KEYS + ["Split"],
        "feature_columns": full_features,
        "base_features_from_step25": base_cols,
        "added_past_only_features": new_cols,
        "target_columns": targets,
        "feature_count": len(full_features), "target_count": len(targets),
        "fit": "Lag imputer and complete-input scaler fitted ONLY on training rows",
        "chronology": "Historical shift(1)/rolling computed from raw warmup, train, gap, validation, inference_only, test date history; uses no future target columns",
        "history_requirement": "Inference MUST supply prior observation history by disease and block; derived lag columns require chronological historical context",
        "inference_preprocessing": "Use trusted Step 25 saved base preprocessor, then derive past-only lag columns, apply saved Step 26 lag imputer and full scaler where needed",
        "data_provenance": "Synthetic disease observations and toy estate graph; NASA point location unverified",
        "scientific_evaluation": "Not real-estate validated; no test set metric calculated",
    }
    write_json(process_dir / "multidisease_feature_contract.json", final_contract)
    report = {
        "status": "PASS_SIMULATED_FEATURE_ENGINEERING",
        "rows": counts,
        "history_rows_including_gap_and_warmup": len(history),
        "diseases": contract25["diseases"],
        "predictors_step25": len(base_cols),
        "past_only_predictors_added": len(new_cols),
        "total_features": len(full_features),
        "targets": len(targets),
        "pre_imputation_missing_by_split": missing_by_split,
        "imputer_and_scaler_fit": "train_only",
        "label_based_feature_computation": False,
        "data_scope": "Simulation only; no model trained/evaluated",
    }
    write_json(report_dir / "step26_multidisease_feature_engineering_summary.json", report)
    print("=" * 76)
    print("STEP 26 - MULTI-DISEASE PAST-ONLY FEATURE ENGINEERING (SIMULATION)")
    print("=" * 76)
    print(f"Historical origin rows: {len(history)} | Model-ready: {sum(counts.values())}")
    print(f"Train/validation/test rows: {counts}")
    print(f"Previous features: {len(base_cols)} | New historical: {len(new_cols)} | Total: {len(full_features)}")
    print(f"Forecast targets: {len(targets)} | Disease classes: {len(contract25['diseases'])}")
    print("Lag and rolling windows strictly use PRIOR days (shift 1).")
    print("Imputer and complete scaler fitted on TRAIN ONLY.")
    print("Saved:", process_dir / "multidisease_feature_contract.json")
    print("Saved:", artifact)
    print("Report:", report_dir / "step26_multidisease_feature_engineering_summary.json")
    print("PASS: no target columns were accessed for new feature derivation; test metrics NOT computed.")
    print("CAUTION: Synthetic labels and estate blocks, unverified source climate location.")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--component-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = p.parse_args()
    create(args.component_root)
