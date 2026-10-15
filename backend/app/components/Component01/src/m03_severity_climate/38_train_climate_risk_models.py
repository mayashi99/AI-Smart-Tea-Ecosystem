#!/usr/bin/env python3
"""Step 38: train and validate CLIMATE-ONLY synthetic day-7 disease-risk proxies.

LEAKAGE SAFETY: reads Step37 TRAIN and VALIDATION + contract only.
Never loads the Step37 LOCKED TEST. Models trained at DATE x DISEASE grain
because same-day NASA point weather repeats identically across 16 blocks.
"""
from __future__ import annotations

import argparse
import json
from datetime import timedelta
from pathlib import Path
import sys
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from climate_risk_inference import (TARGETS, DISEASES, MODEL_REL,
                                    predict_climate_background, _model_scores)

DEFAULT_ROOT = Path(__file__).resolve().parents[2]
TRAIN_REL = 'data/processed/climate_risk_step37_train.csv'
VAL_REL = 'data/processed/climate_risk_step37_validation.csv'
CONTRACT_REL = 'data/processed/climate_risk_step37_contract.json'


def require(ok: bool, why: str) -> None:
    if not ok:
        raise ValueError(why)


def load_split(root: Path, filename: str, split: str, features: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    path = root / filename
    require(path.is_file(), f'Step37 {split} missing: {path}')
    needed = ['Forecast_Origin_Date', 'Forecast_Target_Date', 'Block_ID', 'Disease_Name', 'Split',
              *features, *TARGETS]
    frame = pd.read_csv(path)
    require(set(needed).issubset(frame), f'{split} missing columns: {sorted(set(needed)-set(frame))}')
    require(frame.Split.eq(split).all(), f'{split} contains other split values')
    require(frame.Disease_Name.notna().all() and set(frame.Disease_Name.unique()) == set(DISEASES),
            f'{split}: incorrect disease set')
    for c in ('Forecast_Origin_Date', 'Forecast_Target_Date'):
        frame[c] = pd.to_datetime(frame[c], errors='coerce')
        require(frame[c].notna().all(), f'{split}: invalid {c}')
    require((frame.Forecast_Target_Date - frame.Forecast_Origin_Date).dt.days.eq(7).all(),
            f'{split}: target horizon not exactly 7 days')
    require(frame[needed].notna().all().all(), f'{split}: null in required values')
    require(not frame.duplicated(['Forecast_Origin_Date','Disease_Name','Block_ID']).any(),
            f'{split}: duplicated date/disease/block')
    require(set(frame.Block_ID.unique()) == {f'B{i:02d}' for i in range(1, 17)},
            f'{split}: expected block IDs B01..B16')
    require(frame.groupby(['Forecast_Origin_Date','Disease_Name']).size().eq(16).all(),
            f'{split}: 16 simulated blocks required per date/disease')
    require(frame.groupby('Forecast_Origin_Date').size().eq(64).all(),
            f'{split}: full 4 diseases by 16 blocks coverage required each date')
    require(not np.isnan(frame[features].to_numpy(dtype=float)).any() and
            np.isfinite(frame[features].to_numpy(dtype=float)).all(),
            f'{split}: invalid numeric features')
    for t in TARGETS:
        require(frame[t].isin((0, 1)).all(), f'{split}: targets must be binary')
    groups = frame.groupby(['Forecast_Origin_Date', 'Disease_Name'], sort=True)
    for f in features:
        spread = groups[f].max() - groups[f].min()
        require((spread.abs() <= 1e-6).all(),
                f'{split}: climate feature {f} varies by block (aggregation invalid)')
    # DO NOT treat 16 repeats of one weather observation as independent climate data.
    grouped = groups[features].first()
    for t in TARGETS:
        grouped[t] = groups[t].mean()
    grouped = grouped.reset_index()
    require(len(grouped) * 16 == len(frame), f'{split}: incomplete grouping')
    return frame, grouped


def candidates() -> dict:
    # Fast CPU-only, no GPU/extra packages needed. All fitting uses train only.
    return {
        'RIDGE': make_pipeline(StandardScaler(), Ridge(alpha=15.0)),
        'HIST_GB': HistGradientBoostingRegressor(max_iter=125, learning_rate=.055,
                    max_leaf_nodes=9, min_samples_leaf=22, l2_regularization=1., random_state=38),
        'RANDOM_FOREST': RandomForestRegressor(n_estimators=100, max_depth=8,
                    min_samples_leaf=7, max_features=.85, n_jobs=-1, random_state=38),
    }


def metrics(y: np.ndarray, p: np.ndarray) -> dict:
    require(len(y) == len(p) and len(y) > 0, 'Metric arrays mismatch')
    p = np.clip(np.asarray(p, dtype=float), 1e-8, 1-1e-8)
    y = np.asarray(y, dtype=float)
    # The individual binary labels (16 blocks) have variance within each group.
    # This analytic 'block Brier' equals average binary Brier, without pretending
    # 16 identical climate records are independent observations.
    brier = float(np.mean(y*(1.-p)**2 + (1.-y)*p**2))
    logloss = float(np.mean(-y*np.log(p) - (1.-y)*np.log(1.-p)))
    return {
        'date_disease_observations': int(len(y)),
        'positive_fraction_mean': round(float(y.mean()), 6),
        'aggregated_prevalence_mae': round(float(np.mean(np.abs(y-p))), 6),
        'aggregated_prevalence_rmse': round(float(np.sqrt(np.mean((y-p)**2))), 6),
        'analytic_block_brier_correlated': round(brier, 6),
        'analytic_block_log_loss_correlated': round(logloss, 6),
    }


def train(root: Path) -> dict:
    start = time.time()
    root = root.resolve()
    contract_file = root / CONTRACT_REL
    require(contract_file.is_file(), f'Step37 contract missing: {contract_file}')
    contract = json.loads(contract_file.read_text(encoding='utf-8'))
    require(contract.get('schema_version') == 'step37-v1', 'Unrecognized Step37 contract')
    require(contract.get('nasa_location_verified_for_target_estate') is False,
            'This training is designed for unverified-climate-location SIMULATION only')
    features = contract['features']
    require(len(features) == 18 and len(set(features)) == 18 and contract['targets'] == list(TARGETS),
            'Unexpected feature/target contract')
    train_rows, train_g = load_split(root, TRAIN_REL, 'train', features)
    val_rows, val_g = load_split(root, VAL_REL, 'validation', features)
    require(train_rows.Forecast_Target_Date.max() < val_rows.Forecast_Origin_Date.min(),
            'Target overlap or missing chronological embargo between train & validation')
    require(set(train_rows.Forecast_Origin_Date).isdisjoint(set(val_rows.Forecast_Origin_Date)),
            'Train/validation dates overlap')
    require(len(train_rows) == 45440 and len(val_rows) == 22464,
            'Expected Step37 complete training and validation counts')

    x_train = train_g[features].to_numpy(dtype=float)
    x_val = val_g[features].to_numpy(dtype=float)
    saved_models, selected, rates, comparison, val_scores = {}, {}, {}, [], {}
    for target in TARGETS:
        y_train = train_g[target].to_numpy(dtype=float)
        y_val = val_g[target].to_numpy(dtype=float)
        rates[target] = {d: float(train_g.loc[train_g.Disease_Name.eq(d), target].mean()) for d in DISEASES}
        base_preds = val_g.Disease_Name.map(rates[target]).to_numpy(dtype=float)
        all_predictions = {'TRAIN_DISEASE_BASELINE': base_preds}
        for name, model in candidates().items():
            model.fit(x_train, y_train)
            saved_models[f'{target}::{name}'] = model
            all_predictions[name] = np.clip(np.asarray(model.predict(x_val), dtype=float), 0., 1.)
        # Validation-only selection: baseline is eligible; require >0.0001
        # absolute Brier improvement to choose a more complex ML predictor.
        for name, pred in all_predictions.items():
            m = metrics(y_val, pred)
            comparison.append({'target': target, 'candidate': name, 'validation': m})
        sorted_names = sorted(all_predictions, key=lambda name:
                              (metrics(y_val, all_predictions[name])['analytic_block_brier_correlated'],
                               name != 'TRAIN_DISEASE_BASELINE'))
        best_name = sorted_names[0]
        baseline_brier = metrics(y_val, base_preds)['analytic_block_brier_correlated']
        best_brier = metrics(y_val, all_predictions[best_name])['analytic_block_brier_correlated']
        if baseline_brier - best_brier < .0001:
            best_name = 'TRAIN_DISEASE_BASELINE'
        val_scores[target] = all_predictions[best_name]
        selected[target] = {
            'name': best_name,
            'validation_metrics': metrics(y_val, val_scores[target]),
            'baseline_brier': baseline_brier,
            'selection_rule': 'Minimum validation Brier; require >=0.0001 absolute gain over train-only disease baseline.'
        }

    bundle = {
        'schema': 'step38-climate-risk-v1',
        'step': 38,
        'status': 'SYNTHETIC_CLIMATE_ONLY_VALIDATION_SELECTED',
        'features': list(features),
        'climate_features': list(features[:12]),
        'targets': list(TARGETS),
        'diseases': list(DISEASES),
        'selected': selected,
        'train_disease_rates': rates,
        'models': saved_models,
        'nasa_point': {'latitude': contract.get('nasa_point_latitude'),
                       'longitude': contract.get('nasa_point_longitude')},
        'nasa_estate_location_verified': False,
        'split': {'train_origins': int(train_g.Forecast_Origin_Date.nunique()),
                  'validation_origins': int(val_g.Forecast_Origin_Date.nunique()),
                  'locked_test_evaluated': False},
        'modelling_granularity': 'Date x disease; same date/disease background score for all 16 blocks',
        'warning': 'Simulated labels, single NASA point not estate matched; not field-validated risk.'
    }
    output_model = root / MODEL_REL
    output_model.parent.mkdir(parents=True, exist_ok=True)
    report_dir = root / 'outputs/reports'
    dashboard_dir = root / 'outputs/dashboard/climate'
    report_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, output_model, compress=3)
    # Verify persisted model parity with in-memory validation predictions
    loaded_bundle = joblib.load(output_model)
    loaded_preds = _model_scores(loaded_bundle, val_g)
    for t in TARGETS:
        require(np.allclose(loaded_preds[t], val_scores[t], atol=1e-9),
                f'Persisted model mismatch for {t}')
    origin = '2025-12-24'  # within validation period; not from locked test
    snapshot = predict_climate_background(root, origin, loaded_bundle)
    require(len(snapshot) == 4 and {r['Disease_Name'] for r in snapshot} == set(DISEASES),
            'Snapshot inference failed')
    # Dashboard snapshot contains PREDICTIONS ONLY (not validation target observations)
    snapshot_path = dashboard_dir / 'step38_climate_risk_validation_snapshot.csv'
    pd.DataFrame(snapshot).to_csv(snapshot_path, index=False)
    registry_path = output_model.parent / 'climate_risk_registry.json'
    report_path = report_dir / 'step38_m03_climate_model_validation.json'
    infer_date = 'end-of-day observed NASA weather; 7-day synthetic proxy targets'
    registry = {k:v for k,v in bundle.items() if k not in ('models', 'train_disease_rates')}
    registry['snapshot_origin'] = origin
    registry['snapshot_path'] = str(snapshot_path.relative_to(root))
    registry_path.write_text(json.dumps(registry, indent=2, allow_nan=False), encoding='utf-8')
    audit = {
        'step': 38,
        'status': 'PASS_SYNTHETIC_CLIMATE_ONLY_TRAINING_VALIDATION_NOT_FIELD_VALIDATED',
        'source_step37_contract': CONTRACT_REL,
        'training_rows_original': int(len(train_rows)),
        'validation_rows_original': int(len(val_rows)),
        'training_date_disease_groups': int(len(train_g)),
        'validation_date_disease_groups': int(len(val_g)),
        'train_origin_start': str(train_g.Forecast_Origin_Date.min().date()),
        'train_origin_end': str(train_g.Forecast_Origin_Date.max().date()),
        'validation_origin_start': str(val_g.Forecast_Origin_Date.min().date()),
        'validation_origin_end': str(val_g.Forecast_Origin_Date.max().date()),
        'model_selection': selected,
        'all_validation_candidates': comparison,
        'outputs': {'model': str(output_model.relative_to(root)),
                    'registry': str(registry_path.relative_to(root)),
                    'snapshot': str(snapshot_path.relative_to(root))},
        'locked_test_opened': False,
        'future_weather_used': False,
        'observation_conditioned_dynamic_reforecast': False,
        'fixed_climate_location': contract.get('nasa_point_latitude'),
        'weather_origin_note': infer_date,
        'elapsed_seconds': round(time.time()-start, 2),
        'limitations': [
            'Only synthetic targets were used, no real-estate disease outcome validation.',
            'NASA coordinates 6.7789,79.9301 have not been mapped to a Nuwara Eliya estate.',
            'This produces SAME climate background risk across 16 blocks; m04 required for block-specific risk.',
            'Random split avoided; validation outcomes used only for selection; Step37 locked test untouched.',
            'The risk-band boundaries are illustrative, not scientifically calibrated alert thresholds.',
            'Disease incidence counts do not establish leaf lesion-area severity.',
        ]
    }
    report_path.write_text(json.dumps(audit, indent=2, allow_nan=False), encoding='utf-8')
    print('='*78)
    print('STEP 38 - SYNTHETIC CLIMATE-ASSOCIATED DAY-7 DISEASE RISK | MODEL TRAINING')
    print('='*78)
    print(f'Training rows={len(train_rows)} | train date x disease groups={len(train_g)}')
    print(f'Validation rows={len(val_rows)} | validation date x disease groups={len(val_g)}')
    print(f'Model candidates: TRAIN_DISEASE_BASELINE, RIDGE, HIST_GB, RANDOM_FOREST')
    for t in TARGETS:
        c = selected[t]
        print(f"{t}: selected={c['name']} | val_brier={c['validation_metrics']['analytic_block_brier_correlated']:.6f} "
              f"| train_base_brier={c['baseline_brier']:.6f}")
    print('Saved model:', output_model)
    print('Validation-only dashboard snapshot:', snapshot_path, '| records=4')
    print('Registry:', registry_path)
    print('Report:', report_path)
    print('PASS: Trained, validation-selected and reload-verified climate-only simulated models.')
    print('TEST LOCKED: NOT OPENED. No future weather used.')
    print('WARNING: Shared single-point climate, not block-specific, not Nuwara Eliya verified.')
    return audit


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--component-root', default=str(DEFAULT_ROOT), type=Path)
    args = p.parse_args()
    train(args.component_root)


if __name__ == '__main__':
    main()
