"""Step 27 — validated chronological sequence indexes for simulated 4-disease estate.

Produces compact day tensors and safe sliding-window indices for 14-day LSTM /
GCN-LSTM training. Windows NEVER cross split boundaries. Targets are next 7 days.
No model training and no performance evaluation happens here.
"""
from __future__ import annotations

import argparse
import json
from datetime import timedelta
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

SPLITS = ("train", "validation", "test")
KEYS = ("Forecast_Origin_Date", "Estate_ID", "Block_ID", "Disease_Name")
Y_KINDS = ("Target_Disease_Active", "Target_Incidence_Pct", "Target_New_Onset_By")


def ensure(condition, message):
    if not condition:
        raise RuntimeError(message)


def root_from_file():
    # Component01/src/m04_disease_spread/<this file>
    return Path(__file__).resolve().parents[2]


def clean_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_graph(root):
    blocks = pd.read_csv(root / "data/synthetic/estate_blocks.csv")
    edges = pd.read_csv(root / "data/synthetic/block_adjacency.csv")
    ensure({"Block_ID", "Estate_ID"}.issubset(blocks), "Invalid estate_blocks.csv")
    ensure({"Source_Block", "Target_Block"}.issubset(edges), "Invalid adjacency CSV")
    ensure(len(blocks) == 16 and blocks.Block_ID.is_unique, "Exactly 16 unique demo blocks required")
    ensure(blocks.Estate_ID.nunique() == 1, "This prototype is one estate only")
    block_ids = sorted(blocks.Block_ID.astype(str).tolist())
    ensure(len(edges) == 48, "Expected 48 directed dummy edges")
    ensure(not edges.duplicated(["Source_Block", "Target_Block"]).any(), "Duplicate graph edges")
    ensure((edges.Source_Block != edges.Target_Block).all(), "Self edges must not be in the source graph")
    index = {name: j for j, name in enumerate(block_ids)}
    adjacency = np.zeros((16, 16), dtype=np.float32)
    for src, dest in edges[["Source_Block", "Target_Block"]].itertuples(index=False, name=None):
        ensure(src in index and dest in index, f"Unknown block in graph: {src}, {dest}")
        adjacency[index[src], index[dest]] = 1.0
    ensure(np.array_equal(adjacency, adjacency.T), "Demo adjacency must be symmetric")
    ensure(int(adjacency.sum()) == 48, "Missing expected directed edges")
    # Kipf-Welling normalized graph with self loops; shared by every disease.
    with_loops = adjacency + np.eye(16, dtype=np.float32)
    degree = with_loops.sum(axis=1)
    inverse_sqrt = np.power(degree, -0.5)
    norm_adj = inverse_sqrt[:, None] * with_loops * inverse_sqrt[None, :]
    return block_ids, str(blocks.Estate_ID.iloc[0]), adjacency, norm_adj.astype(np.float32)


def validate_target_dates(root, keyed_frames):
    """Recheck every target date against forecast origin, without using labels as predictors."""
    source = root / "data/synthetic/synthetic_block_records_multidisease.csv"
    columns = list(KEYS) + [f"Target_Date_Day_{day}" for day in range(1, 8)] + ["Split"]
    raw = pd.read_csv(source, usecols=columns, low_memory=False)
    raw = raw[raw.Split.isin(SPLITS)].copy()
    raw["Forecast_Origin_Date"] = pd.to_datetime(raw["Forecast_Origin_Date"], errors="raise")
    ensure(not raw.duplicated(list(KEYS)).any(), "Source date check contains duplicate origin keys")
    for day in range(1, 8):
        values = pd.to_datetime(raw[f"Target_Date_Day_{day}"], errors="coerce")
        ensure(values.notna().all(), f"Missing target date Day {day}")
        ensure((values - raw.Forecast_Origin_Date).eq(pd.Timedelta(days=day)).all(),
               f"Target date alignment failed: day {day}")
    for split in SPLITS:
        tab = raw[raw.Split == split]
        expected = keyed_frames[split]
        ensure(len(tab) == len(expected), f"Raw target date row count mismatch: {split}")
        ensure(tab[list(KEYS)].astype(str).sort_values(list(KEYS)).reset_index(drop=True).equals(
            expected[list(KEYS)].astype(str).sort_values(list(KEYS)).reset_index(drop=True)),
            f"Raw target date keys mismatch Step26: {split}")
    return len(raw)


def build_one_split(frame, split, features, target_columns, disease_names, block_ids, scaler, length, estate_id):
    ensure(frame.Split.eq(split).all(), f"Split mismatch in {split}")
    ensure(frame[list(KEYS)].notna().all().all(), f"Null keys {split}")
    ensure(not frame.duplicated(list(KEYS)).any(), f"Repeated row key {split}")
    ensure(set(frame.Block_ID) == set(block_ids), f"Missing/unknown block {split}")
    ensure(set(frame.Disease_Name) == set(disease_names), f"Missing/unknown disease {split}")
    ensure(frame.Estate_ID.eq(estate_id).all(), f"Wrong estate in {split}")
    ensure(set(features + target_columns).issubset(frame.columns), f"Missing features or targets {split}")
    ensure(not any(c.startswith("Target_") for c in features), "Target leakage into predictor whitelist")
    ensure(not set(features).intersection(target_columns), "Target listed as feature")
    origin = pd.to_datetime(frame.Forecast_Origin_Date, errors="raise")
    ensure(origin.notna().all(), f"Missing dates in {split}")
    frame = frame.copy()
    frame["Forecast_Origin_Date"] = origin
    dates = pd.DatetimeIndex(sorted(frame.Forecast_Origin_Date.unique()))
    ensure(len(dates) >= length, f"Split {split} shorter than sequence length {length}")
    ensure(((dates[1:] - dates[:-1]) == pd.Timedelta(days=1)).all(),
           f"Nonconsecutive dates within {split} would invalidate sliding windows")
    expected_rows = len(dates) * len(disease_names) * len(block_ids)
    ensure(len(frame) == expected_rows, f"Incomplete disease/block/day grid for {split}")
    frame.Disease_Name = pd.Categorical(frame.Disease_Name, categories=disease_names, ordered=True)
    frame.Block_ID = pd.Categorical(frame.Block_ID, categories=block_ids, ordered=True)
    frame = frame.sort_values(["Forecast_Origin_Date", "Disease_Name", "Block_ID"])
    ensure(frame.groupby(["Forecast_Origin_Date", "Disease_Name"], observed=True).size().eq(16).all(),
           f"Incomplete 16-block snapshots for {split}")
    arr = frame[features].to_numpy(dtype=np.float64)
    ensure(np.isfinite(arr).all(), f"Invalid/unimputed features in {split}")
    scaled = scaler.transform(arr).astype(np.float32, copy=False)  # fitted ONLY on train in Step26
    ensure(np.isfinite(scaled).all(), f"Invalid scaled features in {split}")
    x = scaled.reshape(len(dates), len(disease_names), len(block_ids), len(features))
    ys = frame[target_columns].to_numpy(dtype=np.float32).reshape(
        len(dates), len(disease_names), len(block_ids), 7, len(Y_KINDS))
    ensure(np.isfinite(ys).all(), f"Invalid targets in {split}")
    ensure(np.isin(ys[..., 0], [0, 1]).all() and np.isin(ys[..., 2], [0, 1]).all(),
           f"Invalid classification target values {split}")
    ensure(np.all((ys[..., 1] >= 0) & (ys[..., 1] <= 100)), f"Invalid incidence percentages {split}")
    # sample index: [end_date_index, disease_index]. The window is taken dynamically.
    # All 16 nodes share the same origin date; avoids materializing huge overlapping windows.
    sample_indices = np.array([(date_idx, disease_idx)
                               for date_idx in range(length - 1, len(dates))
                               for disease_idx in range(len(disease_names))], dtype=np.int32)
    ensure(len(sample_indices) == (len(dates) - length + 1) * len(disease_names),
           "Sample index size mismatch")
    first_origin, last_origin = dates[0].strftime("%Y-%m-%d"), dates[-1].strftime("%Y-%m-%d")
    return {
        "x": x, "y": ys, "sample_indices": sample_indices,
        "date_strings": dates.strftime("%Y-%m-%d").to_numpy(dtype="U10"),
        "summary": {
            "origin_days": len(dates), "first_origin": first_origin,
            "last_origin": last_origin, "rows": len(frame),
            "sequence_days": length, "sequence_samples": len(sample_indices),
            "X_days_shape": list(x.shape), "Y_days_shape": list(ys.shape),
            "sample_index_shape": list(sample_indices.shape),
            "first_sequence_origin": dates[length-1].strftime("%Y-%m-%d"),
            "last_sequence_origin": last_origin,
        }
    }


def run(root, length):
    ensure(2 <= length <= 90, "Sequence length must be 2 to 90 days")
    base = root / "data/processed"
    contract = json.loads((base / "multidisease_feature_contract.json").read_text(encoding="utf-8"))
    feat = contract["feature_columns"]
    labels = contract["target_columns"]
    names = contract["disease_names"]
    ensure(len(feat) == 48 and len(labels) == 21 and len(names) == 4,
           "Expected 48 features, 21 labels, four diseases from Step26")
    expected_targets = [f"{kind}_Day_{day}" for day in range(1, 8) for kind in Y_KINDS]
    ensure(labels == expected_targets, "Step 26 target ordering mismatch; STOP to prevent incorrect labels")
    prep = joblib.load(base / "multidisease_step26_feature_pipeline.joblib")
    ensure(prep["feature_columns"] == feat and prep["training_only_fit"] is True,
           "Step26 preprocessing artifact/contract mismatch")
    scaler = prep["full_feature_scaler_train_only"]
    ensure(scaler.n_features_in_ == len(feat), "Train scaler input dimension mismatch")
    blocks, estate, adj, norm_adj = load_graph(root)
    frames = {split: pd.read_csv(base / f"multidisease_features_{split}.csv", low_memory=False)
              for split in SPLITS}
    validated_rows = validate_target_dates(root, frames)
    created = {}
    summaries = {}
    for split in SPLITS:
        built = build_one_split(frames[split], split, feat, labels, names, blocks, scaler, length, estate)
        dest = base / f"multidisease_sequence_graph_{split}.npz"
        np.savez_compressed(dest, X_days=built["x"], Y_days=built["y"],
                            sample_indices=built["sample_indices"], dates=built["date_strings"])
        with np.load(dest, allow_pickle=False) as reloaded:
            ensure(reloaded["X_days"].shape == built["x"].shape and
                   reloaded["Y_days"].shape == built["y"].shape and
                   reloaded["sample_indices"].shape == built["sample_indices"].shape,
                   f"NPZ round trip failed: {split}")
        created[split] = str(dest)
        summaries[split] = built["summary"]
    # Re-evaluate chronology with 7-day target coverage; no future target date belongs in earlier split.
    for prior, subsequent in [("train", "validation"), ("validation", "test")]:
        last_target = pd.Timestamp(summaries[prior]["last_origin"]) + pd.Timedelta(days=7)
        first_next_origin = pd.Timestamp(summaries[subsequent]["first_origin"])
        ensure(last_target < first_next_origin,
               f"7-day embargo violation: {prior} vs {subsequent}")
    graph_path = base / "multidisease_graph_adjacency.npz"
    np.savez_compressed(graph_path, adjacency=adj, adjacency_normalized=norm_adj,
                        block_ids=np.asarray(blocks, dtype="U4"))
    contract27 = {
        "schema_version": "step27-v1", "data_provenance": "SYNTHETIC_MULTI_DISEASE_16_BLOCK_GRID",
        "disease_names": names, "block_ids": blocks, "estate_id": estate,
        "split_names": list(SPLITS), "sequence_days": length,
        "input_feature_columns": feat, "target_columns": labels,
        "target_order_in_Y": ["disease_active_binary", "incidence_percent", "new_onset_binary"],
        "tensor_layout": {
            "X_days": "[n_origin_days, 4_diseases, 16_blocks, 48_train_scaled_features]",
            "Y_days": "[n_origin_days, 4_diseases, 16_blocks, 7_future_days, 3_target_kinds]",
            "sample_indices": "[n_sequence_samples, 2]: [end_day_idx, disease_idx]",
        },
        "window_usage": "For each [end_idx, disease_idx], X_days[end_idx-sequence_days+1:end_idx+1,disease_idx] -> [sequence_days,16,48]. Y_days[end_idx,disease_idx] -> [16,7,3]",
        "lstm_usage": "For per-block LSTM choose one node: X_window[:,block_idx,:] -> [sequence_days,48], labels Y_window[block_idx] -> [7,3]",
        "gcn_lstm_usage": "For graph model keep all nodes: X_window -> [sequence_days,16,48], labels -> [16,7,3], adjacency_normalized -> [16,16]",
        "scaling": "TRAIN_ONLY: Step26 full_feature_scaler_train_only, no fitting on validation/test",
        "no_cross_split_windows": True, "historical_gap_handling": "Sequence windows strictly within each split; first sequence_days-1 origins of each split excluded from sequence samples",
        "target_validation": "All seven target dates align with origin+1..+7, source raw checked",
        "new_model_trained": False, "test_metrics_computed": False,
        "real_world_validation": False,
        "limitations": "All disease activity and officer observations simulated; block map dummy; NASA source geography unconfirmed",
    }
    clean_json(base / "multidisease_sequence_graph_contract.json", contract27)
    report = {
        "status": "PASS_SEQUENCE_GRAPH_PREPARATION_SYNTHETIC_ONLY",
        "raw_target_date_rows_verified": validated_rows,
        "feature_count": len(feat), "target_count": len(labels),
        "blocks": len(blocks), "directed_edges": int(adj.sum()), "disease_count": len(names),
        "sequence_length_days": length, "split_summaries": summaries,
        "files": created, "graph_file": str(graph_path),
        "split_history_policy": "No sequences crossing train/validation/test; embargo checks PASS",
        "training_only_scaling": True, "test_metric_computation": False,
        "source_scope": "Synthetic four-disease, single-site historical climate, 16 mock blocks"
    }
    clean_json(root / "outputs/reports/step27_sequence_graph_summary.json", report)
    print("=" * 77)
    print("STEP 27 - CHRONOLOGICAL SEQUENCE + GRAPH PREPARATION (SIMULATION)")
    print("=" * 77)
    print(f"Features={len(feat)} | Labels={len(labels)} | Diseases={len(names)} | Blocks={len(blocks)} | Directed edges={int(adj.sum())}")
    print(f"Lookback={length} days; future forecast=7 days; scaled using TRAIN only")
    for split in SPLITS:
        s = summaries[split]
        print(f"{split:<12}: origin_days={s['origin_days']:<4} sequence_samples={s['sequence_samples']:<5} X_days={s['X_days_shape']} Y_days={s['Y_days_shape']}")
    print("PASS: all 7-day target dates correct, embargo OK, split windows isolated, graph and arrays verified")
    print("NO models trained; NO validation/test scores computed")
    print("WARNING: only synthetic data; not real estate disease forecasting validation")
    print("Contract:", base / "multidisease_sequence_graph_contract.json")
    print("Report  :", root / "outputs/reports/step27_sequence_graph_summary.json")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None, help="Override Component01 root (for testing)")
    parser.add_argument("--lookback", type=int, default=14)
    args = parser.parse_args()
    run((args.root or root_from_file()).resolve(), args.lookback)


if __name__ == "__main__":
    main()
