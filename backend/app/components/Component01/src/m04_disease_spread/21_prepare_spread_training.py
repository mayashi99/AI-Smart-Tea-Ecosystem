"""Step 21: turn existing 7-day simulated block records into leakage-screened ML inputs.

This does not train a model or claim real-world estate validation. The forecast
origin is END OF DAY; all current-day values must be known when inference runs.
Requires: pandas, numpy. Run from any working directory.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

BASE_FEATURES = [
    "Observation_Available", "Inspected_Bushes", "Symptomatic_Bushes",
    "Sample_Incidence_Pct", "Latest_Observed_Incidence_Pct",
    "Days_Since_Last_Inspection", "T2M", "RH2M", "PRECTOTCORR",
    "ALLSKY_SFC_SW_DWN", "Humidity_Mean_7D", "Rainfall_Sum_7D",
    "Neighbor_Latest_Incidence_Mean_Pct", "Neighbor_Recent_Positive_Count",
]
STATIC_FEATURES = ["Grid_Row", "Grid_Column", "Relative_Vulnerability"]
CALENDAR_FEATURES = ["Day_Of_Year_Sin", "Day_Of_Year_Cos", "Weekday_Sin", "Weekday_Cos"]
FEATURES = BASE_FEATURES + STATIC_FEATURES + CALENDAR_FEATURES
TARGETS = [f"Target_{suffix}_Day_{h}" for h in range(1, 8)
           for suffix in ("Disease_Active", "Incidence_Pct", "New_Onset_By")]
SPLITS = ("train", "validation", "test")
META = ["Forecast_Origin_Date", "Estate_ID", "Block_ID", "Disease_Name", "Split"]


def require_columns(frame: pd.DataFrame, cols: list[str], name: str):
    missing = sorted(set(cols) - set(frame.columns))
    if missing:
        raise ValueError(f"{name} missing required columns: {missing}")


def assert_condition(condition: bool, message: str):
    if not condition:
        raise ValueError(message)


def dt_iso_minmax(values: pd.Series) -> dict[str, str]:
    return {"first_origin": str(values.min().date()), "last_origin": str(values.max().date())}


def build(component: Path):
    component = component.resolve()
    synthetic = component / "data" / "synthetic"
    processed = component / "data" / "processed"
    reports = component / "outputs" / "reports"
    processed.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)

    records = pd.read_csv(synthetic / "synthetic_block_records.csv", encoding="utf-8-sig", low_memory=False)
    blocks = pd.read_csv(synthetic / "estate_blocks.csv", encoding="utf-8-sig")
    edges = pd.read_csv(synthetic / "block_adjacency.csv", encoding="utf-8-sig")
    required = META + BASE_FEATURES + TARGETS + ["Date", "Forecast_Horizon_Days", "All_7_Targets_Available"]
    required += [f"Target_Date_Day_{h}" for h in range(1, 8)]
    require_columns(records, required, "synthetic_block_records.csv")
    require_columns(blocks, ["Block_ID", "Estate_ID"] + STATIC_FEATURES, "estate_blocks.csv")
    require_columns(edges, ["Source_Block", "Target_Block"], "block_adjacency.csv")
    assert_condition(len(records) > 0, "Main data is empty")
    assert_condition(len(blocks) == blocks["Block_ID"].nunique(), "Block_ID duplicated in block metadata")
    assert_condition(not records.duplicated(["Date", "Estate_ID", "Block_ID", "Disease_Name"]).any(),
                     "Duplicate date/estate/block/disease records")
    assert_condition(records["Block_ID"].isin(blocks["Block_ID"]).all(), "Unknown Block_ID in main records")
    assert_condition(records["Forecast_Horizon_Days"].eq(7).all(), "Expected 7-day forecast horizon")
    assert_condition(records["Split"].isin([*SPLITS, "gap", "warmup", "inference_only"]).all(),
                     "Unexpected split labels")
    assert_condition(records["Disease_Name"].nunique() == 1 and records["Disease_Name"].iloc[0] == "Red Rust",
                     "This synthetic spread data and training contract are RED RUST ONLY")

    for col in ("Date", "Forecast_Origin_Date") + tuple(f"Target_Date_Day_{h}" for h in range(1, 8)):
        records[col] = pd.to_datetime(records[col], errors="raise")
    assert_condition((records["Date"] == records["Forecast_Origin_Date"]).all(),
                     "Date != Forecast_Origin_Date")

    if not records["Estate_ID"].eq(blocks["Estate_ID"].iloc[0]).all():
        raise ValueError("Main records and block metadata refer to different estates")
    blocks = blocks.copy()
    blocks["Block_ID"] = blocks["Block_ID"].astype(str)
    edges["Source_Block"] = edges["Source_Block"].astype(str)
    edges["Target_Block"] = edges["Target_Block"].astype(str)
    block_ids = sorted(blocks["Block_ID"].tolist())
    known = set(block_ids)
    assert_condition(edges["Source_Block"].isin(known).all() and edges["Target_Block"].isin(known).all(),
                     "Edge refers to unknown block")
    assert_condition(not (edges["Source_Block"] == edges["Target_Block"]).any(), "Self-link in graph")
    assert_condition(not edges.duplicated(["Source_Block", "Target_Block"]).any(), "Duplicate graph edge")

    valid_rows = records["Split"].isin(SPLITS)
    assert_condition(records.loc[valid_rows, "All_7_Targets_Available"].eq(1).all(),
                     "Some labelled train/validation/test rows do not have all 7 targets")
    selected = records.loc[valid_rows].copy()
    for horizon in range(1, 8):
        col = f"Target_Date_Day_{horizon}"
        assert_condition((selected[col] == selected["Forecast_Origin_Date"] + pd.Timedelta(days=horizon)).all(),
                         f"Forecast date misalignment in {col}")
    for target in TARGETS:
        selected[target] = pd.to_numeric(selected[target], errors="coerce")
        assert_condition(selected[target].notna().all(), f"Missing target in eligible labelled rows: {target}")
        if "Active" in target or "Onset" in target:
            assert_condition(selected[target].isin([0, 1]).all(), f"Non-binary target: {target}")
        else:
            assert_condition(selected[target].between(0, 100).all(), f"Incidence outside 0..100: {target}")

    # Training and test targets must not encroach into the next partition's origin dates.
    boundaries = {}
    for left, right in (("train", "validation"), ("validation", "test")):
        left_rows = selected[selected["Split"].eq(left)]
        right_rows = selected[selected["Split"].eq(right)]
        assert_condition(not left_rows.empty and not right_rows.empty, f"Missing required split {left}/{right}")
        max_target = left_rows["Forecast_Origin_Date"].max() + pd.Timedelta(days=7)
        min_origin = right_rows["Forecast_Origin_Date"].min()
        assert_condition(max_target < min_origin,
                         f"Temporal leakage risk: {left} targets reach into {right} origins")
        boundaries[f"{left}_to_{right}"] = {
            "previous_last_target": str(max_target.date()),
            "next_first_origin": str(min_origin.date()),
            "days_between": int((min_origin - max_target).days),
        }

    # Join only stable block metadata. NEVER join any future outcome or complete future week.
    selected = selected.merge(blocks[["Block_ID"] + STATIC_FEATURES],
                              on="Block_ID", how="left", validate="many_to_one")
    assert_condition(selected[STATIC_FEATURES].notna().all().all(), "Missing block metadata")
    for feature in BASE_FEATURES + STATIC_FEATURES:
        selected[feature] = pd.to_numeric(selected[feature], errors="coerce")

    origin = selected["Forecast_Origin_Date"]
    doy = origin.dt.dayofyear
    weekday = origin.dt.dayofweek
    selected["Day_Of_Year_Sin"] = np.sin(2 * np.pi * doy / 365.25)
    selected["Day_Of_Year_Cos"] = np.cos(2 * np.pi * doy / 365.25)
    selected["Weekday_Sin"] = np.sin(2 * np.pi * weekday / 7.0)
    selected["Weekday_Cos"] = np.cos(2 * np.pi * weekday / 7.0)

    assert_condition(not any(name.startswith("Target_") for name in FEATURES), "Target leakage in FEATURES")
    assert_condition("Split" not in FEATURES and "All_7_Targets_Available" not in FEATURES,
                     "Split or target availability is used as a predictor")
    assert_condition(selected[FEATURES].replace([np.inf, -np.inf], np.nan).notna().any(axis=0).all(),
                     "A feature has no valid values anywhere")

    # Do not impute here. The next modelling step fits imputation/scalers on TRAIN ONLY.
    output_cols = META + FEATURES + TARGETS
    output = selected[output_cols].sort_values(["Forecast_Origin_Date", "Block_ID"]).reset_index(drop=True)
    file_all = processed / "spread_training_table.csv"
    output.to_csv(file_all, index=False)
    split_counts = {}
    origin_ranges = {}
    for split in SPLITS:
        subset = output[output["Split"].eq(split)]
        assert_condition(not subset.empty, f"Empty {split} split")
        subset.to_csv(processed / f"spread_{split}.csv", index=False)
        split_counts[split] = int(len(subset))
        origin_ranges[split] = dt_iso_minmax(selected.loc[selected["Split"].eq(split), "Forecast_Origin_Date"])

    # Preserve graph direction and node ordering explicitly for reproducible GCN training.
    node_idx = {name: idx for idx, name in enumerate(block_ids)}
    graph_nodes = blocks.set_index("Block_ID").loc[block_ids].reset_index()
    graph_nodes.insert(0, "node_index", list(range(len(block_ids))))
    graph_nodes.to_csv(processed / "spread_graph_nodes.csv", index=False)
    graph_edges = edges[["Source_Block", "Target_Block"]].copy()
    graph_edges["source_index"] = graph_edges["Source_Block"].map(node_idx)
    graph_edges["target_index"] = graph_edges["Target_Block"].map(node_idx)
    graph_edges.to_csv(processed / "spread_graph_edges.csv", index=False)

    missing = {name: int(output[name].isna().sum()) for name in FEATURES if output[name].isna().any()}
    contract = {
        "schema_version": "step21-v1", "task": "7-day Red Rust block spread forecasting (synthetic)",
        "forecast_origin_semantics": "END_OF_DAY. Same-day observations/climate must be available before predicting future days.",
        "metadata_columns": META, "feature_columns": FEATURES, "target_columns": TARGETS,
        "target_families": {name: [f"Target_{name}_Day_{h}" for h in range(1, 8)]
                            for name in ("Disease_Active", "Incidence_Pct", "New_Onset_By")},
        "split_column": "Split", "split_values_for_modeling": list(SPLITS),
        "missing_feature_policy": "Fit imputer ONLY on train and apply to validation/test/inference.",
        "scaling_policy": "Fit scaler ONLY on train if needed (e.g. LSTM/GCN+LSTM).",
        "prohibited_predictors": "ALL Target_*; Split; All_7_Targets_Available; any future weather or outcomes",
        "spatial_scope": "16 dummy 4-neighbor estate blocks; shared NASA POWER single climate point, site match not verified",
        "data_provenance": "SYNTHETIC FIELD/DISEASE observations; observed NASA historical climate",
        "external_validity": "SIMULATION ONLY: cannot claim real plantation accuracy",
        "graph_node_file": "data/processed/spread_graph_nodes.csv",
        "graph_edge_file": "data/processed/spread_graph_edges.csv",
    }
    (processed / "spread_feature_contract.json").write_text(json.dumps(contract, indent=2), encoding="utf-8")

    report = {
        "status": "PASS_DEVELOPMENT_ONLY", "source_rows": int(len(records)),
        "model_ready_labeled_rows": int(len(output)), "excluded_split_counts": {
            name: int((records["Split"] == name).sum()) for name in ("gap", "warmup", "inference_only")},
        "model_split_counts": split_counts, "split_origin_ranges": origin_ranges,
        "temporal_split_boundaries": boundaries, "disease_label": "Red Rust only",
        "estate_blocks": len(blocks), "directed_adjacency_edges": len(edges),
        "predictor_count": len(FEATURES), "target_count": len(TARGETS),
        "missing_feature_counts": missing,
        "next_step": "Train RF/other baselines using explicit feature whitelist and train-fitted preprocessing",
        "warning": "Simulation data; climate site correspondence and real-world model performance NOT validated",
    }
    (reports / "step21_spread_preparation_quality.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("=" * 76)
    print("STEP 21 - SEVEN-DAY SYNTHETIC SPREAD TRAINING PREPARATION")
    print("=" * 76)
    print(f"Source rows: {len(records)} | Model-ready labeled rows: {len(output)}")
    print(f"Disease scope: {records['Disease_Name'].iloc[0]} ONLY (simulation)")
    print(f"Graph nodes: {len(blocks)} | Directed edges: {len(edges)}")
    print(f"Predictors (strict whitelist): {len(FEATURES)} | Next-day targets: {len(TARGETS)}")
    print("Split counts:", split_counts)
    print("Excluded warmup/gap/inference_only:", report["excluded_split_counts"])
    print("Missing feature values (allowed; TRAIN-ONLY imputation later):", missing)
    print("Temporal isolation:", boundaries)
    print("Outputs:", file_all)
    print("Feature contract:", processed / "spread_feature_contract.json")
    print("Quality report:", reports / "step21_spread_preparation_quality.json")
    print("PASS: no models trained; test set remains untouched for modelling.")
    print("CAUTION: Synthetic Red Rust outcomes and dummy estate blocks. Real-world evaluation is not established.")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    build(args.component_root)
