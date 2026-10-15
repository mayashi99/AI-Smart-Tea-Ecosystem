"""Step 23: transparent, deterministic four-disease SIMULATION for prototype research.

Preserves the original Red Rust simulated data. Generates three NEW, independent
illustrative stochastic disease scenarios using current/past climate, block
metadata and graph neighbors. Not epidemiologically calibrated or field-validated.

Requires pandas/numpy. Reads only existing Component01/data/synthetic files.
Outputs separate *_multidisease.csv files; NEVER overwrites the originals.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

DISEASE_CONFIGS = {
    "Brown Blight": dict(seed=841, bias=-2.6, t=-0.25, rh=0.40, rain=0.25, sun=-0.15, neighbor=0.85,
                         onset_factor=0.65, recovery=0.13),
    "Grey Leaf": dict(seed=217, bias=-2.8, t=-0.10, rh=0.65, rain=0.20, sun=-0.10, neighbor=0.70,
                      onset_factor=0.66, recovery=0.15),
    "Red Spider Mite": dict(seed=603, bias=-2.7, t=0.60, rh=-0.35, rain=-0.30, sun=0.18, neighbor=0.65,
                            onset_factor=0.70, recovery=0.17),
}
CLIMATE = ["T2M", "RH2M", "PRECTOTCORR", "ALLSKY_SFC_SW_DWN", "Humidity_Mean_7D", "Rainfall_Sum_7D"]
TARGET_NAMES = ("Disease_Active", "Incidence_Pct", "New_Onset_By")


def ensure(ok: bool, why: str):
    if not ok:
        raise ValueError(why)


def sigmoid(x):
    return 1 / (1 + np.exp(-np.clip(x, -20, 20)))


def build(root: Path):
    root = root.resolve()
    data = root / "data" / "synthetic"
    out_reports = root / "outputs" / "reports"
    out_reports.mkdir(parents=True, exist_ok=True)
    original = pd.read_csv(data / "synthetic_block_records.csv", encoding="utf-8-sig", low_memory=False)
    blocks = pd.read_csv(data / "estate_blocks.csv", encoding="utf-8-sig")
    edges = pd.read_csv(data / "block_adjacency.csv", encoding="utf-8-sig")
    require = ["Date", "Estate_ID", "Block_ID", "Disease_Name", "Split", "Observation_Available",
               "Forecast_Origin_Date", "Forecast_Horizon_Days", "All_7_Targets_Available"] + CLIMATE
    require += [f"Target_{name}_Day_{day}" for name in TARGET_NAMES for day in range(1, 8)]
    ensure(set(require).issubset(original.columns), f"Missing source columns: {sorted(set(require) - set(original.columns))}")
    ensure(original.Disease_Name.eq("Red Rust").all(), "Source should contain Red Rust only. Never run on generated multi-disease file.")
    ensure(set(["Block_ID", "Grid_Row", "Grid_Column", "Relative_Vulnerability"]).issubset(blocks.columns), "Block metadata incomplete")
    ensure(set(["Source_Block", "Target_Block"]).issubset(edges.columns), "Adjacency metadata incomplete")
    ensure(not original.duplicated(["Date", "Estate_ID", "Block_ID", "Disease_Name"]).any(), "Original rows are duplicated")
    ensure(original.Forecast_Horizon_Days.eq(7).all(), "Expected seven-day horizons")
    nodes = sorted(blocks.Block_ID.astype(str).tolist())
    n = len(nodes)
    ensure(n == 16 and blocks.Block_ID.nunique() == 16, "Expected 16 unique estate blocks")
    ensure(original.Block_ID.nunique() == 16, "Source records do not cover all 16 blocks")
    orig = original.copy()
    orig["Date"] = pd.to_datetime(orig["Date"], errors="raise")
    ensure(orig.groupby("Date").Block_ID.nunique().eq(n).all(), "Each day must cover all estate blocks")
    dates = pd.DatetimeIndex(sorted(orig.Date.unique()))
    ensure(len(dates) * n == len(original), "Source should have 16 blocks on every day")
    ensure(((dates[1:] - dates[:-1]) == pd.Timedelta(days=1)).all(), "Non-contiguous dates")
    for climate_col in CLIMATE:
        same_day = orig.groupby("Date")[climate_col].nunique(dropna=False)
        ensure(same_day.eq(1).all(), f"Climate feature {climate_col} differs by block on same day")
    for name in ("Split", "Forecast_Horizon_Days", "All_7_Targets_Available"):
        ensure(orig.groupby("Date")[name].nunique(dropna=False).eq(1).all(), f"{name} inconsistent by day")
    ensure(orig["Estate_ID"].nunique() == 1, "Expected one demo estate")
    estate_id = str(orig.Estate_ID.iloc[0])
    node_id = {block: i for i, block in enumerate(nodes)}
    ensure(set(edges.Source_Block).issubset(node_id) and set(edges.Target_Block).issubset(node_id), "Graph references unknown block")
    neighbors = [[] for _ in nodes]
    for row in edges.itertuples(index=False):
        neighbors[node_id[row.Target_Block]].append(node_id[row.Source_Block])
    ensure(all(neighbors), "Every block must have at least one incoming neighbor")

    grid = blocks.set_index("Block_ID").loc[nodes].reset_index()
    vulnerability = grid.Relative_Vulnerability.to_numpy(dtype=float)
    vulnerability = (vulnerability - np.mean(vulnerability)) / max(0.1, np.std(vulnerability))
    source_daily = orig.sort_values(["Date", "Block_ID"]).drop_duplicates("Date").set_index("Date").loc[dates]
    daily = source_daily[CLIMATE + ["Split", "All_7_Targets_Available"]].reset_index()
    dlen = len(dates)
    # Build same-day predictors from simulated observations, not from future labels.
    date_cols = [f"Target_Date_Day_{h}" for h in range(1, 8)]
    target_cols = [f"Target_{v}_Day_{h}" for h in range(1, 8) for v in TARGET_NAMES]
    original_cols = list(original.columns)
    simulated = []
    simulated_officer = []
    per_disease = {}

    for disease, conf in DISEASE_CONFIGS.items():
        rng = np.random.default_rng(conf["seed"])
        active = np.zeros((dlen, n), dtype=np.int8)
        latent_inc = np.zeros((dlen, n), dtype=float)
        obs = np.zeros((dlen, n), dtype=np.int8)
        inspected = np.full((dlen, n), np.nan)
        symptomatic = np.full((dlen, n), np.nan)
        observed_pct = np.full((dlen, n), np.nan)
        latest_pct = np.zeros((dlen, n))
        days_since = np.full((dlen, n), 999, dtype=int)
        neighbor_mean = np.zeros((dlen, n))
        neighbor_recent_pos = np.zeros((dlen, n), dtype=int)
        last_observed = np.zeros(n)
        last_observed_day = np.full(n, -1, dtype=int)
        recent_positives = np.zeros((7, n), dtype=np.int8)
        current_active = rng.binomial(1, 0.09, size=n).astype(np.int8)
        current_inc = np.where(current_active, rng.uniform(4, 18, size=n), 0.0)

        for t in range(dlen):
            climate = daily.iloc[t]
            temp = (float(climate.T2M) - 26.5) / 3.0
            humid = (float(climate.RH2M) - 84.0) / 15.0
            rain = (min(float(climate.PRECTOTCORR), 35.0) - 7.0) / 15.0
            sun = (float(climate.ALLSKY_SFC_SW_DWN) - 5) / 2.0
            neighbor_prev = np.array([np.mean(current_active[v]) for v in neighbors])
            logit = (conf["bias"] + conf["t"] * temp + conf["rh"] * humid + conf["rain"] * rain +
                     conf["sun"] * sun + conf["neighbor"] * neighbor_prev + 0.20 * vulnerability +
                     rng.normal(0, 0.28, size=n))
            onset_p = np.clip(sigmoid(logit) * conf["onset_factor"], 0.003, 0.4)
            new_onset = (rng.random(n) < onset_p).astype(np.int8)
            recovery_p = np.clip(conf["recovery"] + 0.05 * (1 - neighbor_prev), 0.05, 0.4)
            recover = (rng.random(n) < recovery_p).astype(np.int8)
            current_active = np.where(current_active == 1, (1 - recover), new_onset).astype(np.int8)
            # Synthetic latent percentage of symptomatic bushes, conceptually different
            # from sample-incidence measurements that require inspection.
            severity_drift = 0.77 * current_inc + 0.23 * (10 + 14 * sigmoid(logit))
            current_inc = np.where(current_active, np.clip(severity_drift + rng.normal(0, 3, n), 3, 65), 0.0)
            active[t] = current_active
            latent_inc[t] = np.round(current_inc, 3)

            # Inspection schedule is explicitly simulated independently per disease.
            # Every current-day neighbor feature uses only today/past measurements.
            obs_today = (rng.random(n) < 0.55).astype(np.int8)
            obs[t] = obs_today
            sample_n = rng.integers(25, 46, size=n)
            sick = rng.binomial(sample_n, current_inc / 100)
            inspected[t] = np.where(obs_today == 1, sample_n.astype(float), np.nan)
            symptomatic[t] = np.where(obs_today == 1, sick.astype(float), np.nan)
            observed_pct[t] = np.where(obs_today == 1, 100 * sick / sample_n, np.nan)
            for i in range(n):
                if obs_today[i] == 1:
                    last_observed[i] = observed_pct[t, i]
                    last_observed_day[i] = t
            latest_pct[t] = last_observed
            days_since[t] = np.where(last_observed_day >= 0, t - last_observed_day, 999)
            for i in range(n):
                neighbor_mean[t, i] = float(np.mean(last_observed[neighbors[i]]))
                neighbor_recent_pos[t, i] = int(sum(recent_positives[:, j].sum() for j in neighbors[i]))
            recent_positives[t % 7] = (obs_today & (observed_pct[t] > 0)).astype(np.int8)

        onset_event = (active == 1) & (np.vstack([np.zeros((1, n), dtype=np.int8), active[:-1]]) == 0)
        disease_rows = []
        for t, dt in enumerate(dates):
            climate = daily.iloc[t]
            values = {key: climate[key] for key in CLIMATE}
            split = str(climate["Split"])
            available = int(climate["All_7_Targets_Available"])
            for i, block_id in enumerate(nodes):
                row = dict.fromkeys(original_cols, np.nan)
                row.update(Date=dt.date().isoformat(), Estate_ID=estate_id, Block_ID=block_id,
                           Disease_Name=disease, Observation_Available=int(obs[t, i]),
                           Inspected_Bushes=inspected[t, i], Symptomatic_Bushes=symptomatic[t, i],
                           Sample_Incidence_Pct=observed_pct[t, i],
                           Latest_Observed_Incidence_Pct=round(float(latest_pct[t, i]), 5),
                           Days_Since_Last_Inspection=int(days_since[t, i]),
                           Neighbor_Latest_Incidence_Mean_Pct=round(float(neighbor_mean[t, i]), 5),
                           Neighbor_Recent_Positive_Count=int(neighbor_recent_pos[t, i]),
                           Climate_Source="NASA_POWER_SINGLE_POINT",
                           Observation_Source="SYNTHETIC_MULTIDISEASE_SCENARIO_V1",
                           Forecast_Origin_Date=dt.date().isoformat(),
                           Forecast_Horizon_Days=7, All_7_Targets_Available=available,
                           Split=split, **values)
                for h in range(1, 8):
                    future = t + h
                    row[f"Target_Date_Day_{h}"] = (dt + pd.Timedelta(days=h)).date().isoformat()
                    row[f"Target_Disease_Active_Day_{h}"] = int(active[future, i]) if future < dlen else np.nan
                    row[f"Target_Incidence_Pct_Day_{h}"] = round(float(latent_inc[future, i]), 3) if future < dlen else np.nan
                    row[f"Target_New_Onset_By_Day_{h}"] = int(onset_event[t + 1:min(future + 1, dlen), i].any()) if future < dlen else np.nan
                disease_rows.append(row)
                if obs[t, i]:
                    simulated_officer.append(dict(Observation_ID=f"SIM-MULTI-{conf['seed']}-{dt.strftime('%Y%m%d')}-{block_id}",
                                                 Date=dt.date().isoformat(), Block_ID=block_id,
                                                 Disease_Name=disease, Image_Filename="",
                                                 Inspected_Bushes=int(inspected[t, i]),
                                                 Symptomatic_Bushes=int(symptomatic[t, i]),
                                                 Sample_Incidence_Pct=round(float(observed_pct[t, i]), 5),
                                                 Officer_Confirmed="SIMULATED",
                                                 Observation_Source="SYNTHETIC_MULTIDISEASE_SCENARIO_V1"))
        frame = pd.DataFrame.from_records(disease_rows, columns=original_cols)
        ensure(len(frame) == len(original), f"Wrong row count for {disease}")
        ensure(frame[frame.Split.isin(["train", "validation", "test"])][target_cols].notna().all().all(), f"Missing labeled targets: {disease}")
        per_disease[disease] = {"rows": len(frame), "mean_active_rate": round(float(active.mean()), 4),
                                "mean_incidence_pct": round(float(latent_inc.mean()), 4),
                                "inspections": int(obs.sum())}
        simulated.append(frame)
        print(f"  Built {disease}: {len(frame)} rows; mean active={per_disease[disease]['mean_active_rate']:.3f}", flush=True)

    combined = pd.concat([original] + simulated, ignore_index=True)
    ensure(len(combined) == 4 * len(original), "Unexpected combined row count")
    ensure(not combined.duplicated(["Date", "Estate_ID", "Block_ID", "Disease_Name"]).any(), "Duplicate model row keys")
    expected = {"Brown Blight", "Grey Leaf", "Red Rust", "Red Spider Mite"}
    ensure(set(combined.Disease_Name.unique()) == expected, "Unexpected disease labels")
    # Chronological splits copied from dates only; all four diseases follow same isolation.
    originals_split = original.groupby("Date").Split.first()
    ensure((combined.Split.astype(str).to_numpy() == combined.Date.map(originals_split).astype(str).to_numpy()).all(), "Split changed by disease")
    fullpath = data / "synthetic_block_records_multidisease.csv"
    combined.to_csv(fullpath, index=False, encoding="utf-8")

    out_obs = data / "officer_disease_observations_multidisease.csv"
    prior_officer = pd.read_csv(data / "officer_disease_observations.csv", encoding="utf-8-sig", low_memory=False)
    combined_officer = pd.concat([prior_officer, pd.DataFrame.from_records(simulated_officer)], ignore_index=True)
    ensure(not combined_officer.duplicated(["Observation_ID"]).any(), "Duplicate officer observation IDs")
    combined_officer.to_csv(out_obs, index=False)

    report = {
        "status": "PASS_SIMULATION_ONLY", "original_red_rust_records": len(original),
        "generated_disease_count": 3, "total_diseases": 4, "total_records": len(combined),
        "disease_rows": combined.Disease_Name.value_counts().to_dict(),
        "split_counts": combined.Split.value_counts().to_dict(), "observations_total": len(combined_officer),
        "blocks": n, "days": dlen, "first_date": str(dates.min().date()), "last_date": str(dates.max().date()),
        "generated_disease_summaries": per_disease,
        "method": "Independent stochastic synthetic scenarios parameterized with historical single-site NASA climate, fixed 16-block dummy adjacency, and synthetic inspection counts; original Red Rust synthetic data retained unchanged.",
        "limits": ["NOT real estate observations", "Scenario parameters are illustrative, not disease-validated",
                   "Train/validation/test metrics will measure simulation fitting, not field forecasting performance",
                   "NASA climate source location is not verified to match the intended estate",
                   "End-of-day predictors only; no future weather/targets may enter features",
                   "Unobserved source-disease label variation cannot be inferred from real data here"],
        "next_steps": "24 quality+EDA; 25 preprocessing using training-only fitting; 26 past-only features; 27 temporal split validation; 28 multi-disease model training",
    }
    path_report = out_reports / "step23_multidisease_simulation_summary.json"
    path_report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("=" * 75)
    print("STEP 23 - MULTI-DISEASE SIMULATION PREPARATION")
    print("=" * 75)
    print("Disease rows:", report["disease_rows"])
    print("Split counts:", report["split_counts"])
    print("Source Red Rust unchanged:", data / "synthetic_block_records.csv")
    print("Output:", fullpath)
    print("Officer observations:", out_obs)
    print("Report:", path_report)
    print("PASS: source untouched; 4-disease prototype scenarios created.")
    print("WARNING: SIMULATION ONLY; NOT verified multi-disease agricultural risk models.")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    build(args.component_root)
