"""STEP 28: Train four-disease, seven-day synthetic estate ML baselines.

Contract: Step 26 precomputed 48 feature columns and 21 outcome labels.
Train-only fitting, validation-only model selection, FINAL TEST only after
selection (full mode); smoke mode never reads or evaluates test rows.

These models describe a SYNTHETIC scenario, not validated field disease risk.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, mean_squared_error, precision_score, recall_score

DISEASES = ['Brown Blight', 'Grey Leaf', 'Red Rust', 'Red Spider Mite']
KINDS = ('Disease_Active', 'Incidence_Pct', 'New_Onset_By')
SPLITS = ('train', 'validation', 'test')
META = ['Forecast_Origin_Date', 'Estate_ID', 'Block_ID', 'Disease_Name', 'Split']


def ensure(cond, text):
    if not cond:
        raise RuntimeError(text)


def save_json(file: Path, obj: dict):
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(obj, indent=2, allow_nan=False, default=str) + '\n', encoding='utf-8')


def load_contract(root: Path):
    base = root / 'data' / 'processed'
    contract = json.loads((base / 'multidisease_feature_contract.json').read_text(encoding='utf-8'))
    cols = contract['feature_columns']
    targets = contract['target_columns']
    correct_targets = [f'Target_{kind}_Day_{h}' for h in range(1, 8) for kind in KINDS]
    ensure(len(cols) == 48 and len(set(cols)) == 48, 'Expected Step 26 with 48 unique predictors')
    ensure(targets == correct_targets, 'Step26 target ordering has changed; refusing unsafe training')
    ensure(not set(cols).intersection(targets) and not any(c.startswith('Target_') for c in cols), 'Target leakage in features')
    ensure(set(contract['disease_names']) == set(DISEASES), 'Four-disease Step 26 contract required')
    return cols, targets


def load_split(root: Path, split: str, columns: list[str], targets: list[str]):
    p = root / 'data' / 'processed' / f'multidisease_features_{split}.csv'
    ensure(p.is_file(), f'Missing Step26 file: {p}')
    frame = pd.read_csv(p, usecols=META + columns + targets, low_memory=False)
    ensure(frame.Split.eq(split).all(), f'Incorrect split marker: {split}')
    ensure(set(frame.Disease_Name) == set(DISEASES), f'Disease scope mismatch: {split}')
    ensure(not frame.duplicated(META[:-1]).any(), f'Duplicate origin/block/disease: {split}')
    ensure(frame['Forecast_Origin_Date'].notna().all(), f'Missing dates in {split}')
    ensure(len(frame) > 0, f'Empty {split}')
    check = frame[columns + targets].to_numpy(dtype='float64')
    ensure(np.isfinite(check).all(), f'NaN or inf in precomputed features/labels: {split}')
    return frame


def limit_for_smoke(frame: pd.DataFrame, count: int, seed: int):
    # Includes every disease, but random subset is only for a functionality smoke test.
    n_each = max(20, count // 4)
    segments = []
    for j, disease in enumerate(DISEASES):
        group = frame[frame.Disease_Name.eq(disease)]
        segments.append(group.sample(n=min(len(group), n_each), random_state=seed + j))
    return pd.concat(segments, ignore_index=True)


def make_estimator(name: str, classification: bool, jobs: int, seed: int, smoke: bool, y: np.ndarray):
    n = 30 if smoke else 100
    if name == 'rf':
        kwargs = {'n_estimators': n, 'max_depth': 12 if smoke else 16,
                  'min_samples_leaf': 2, 'n_jobs': jobs, 'random_state': seed}
        return (RandomForestClassifier(class_weight='balanced_subsample', **kwargs)
                if classification else RandomForestRegressor(**kwargs))
    if name == 'lgbm':
        import lightgbm as lgb
        common = {'n_estimators': n, 'learning_rate': 0.06, 'max_depth': -1,
                  'num_leaves': 20 if smoke else 31, 'n_jobs': jobs, 'random_state': seed,
                  'verbosity': -1}
        return (lgb.LGBMClassifier(class_weight='balanced', **common)
                if classification else lgb.LGBMRegressor(**common))
    if name == 'xgb':
        from xgboost import XGBClassifier, XGBRegressor
        common = {'n_estimators': n, 'learning_rate': 0.06, 'max_depth': 4 if smoke else 6,
                  'subsample': 0.9, 'colsample_bytree': 0.9, 'n_jobs': jobs,
                  'random_state': seed, 'tree_method': 'hist'}
        if classification:
            pos = float((y == 1).sum())
            neg = float((y == 0).sum())
            return XGBClassifier(eval_metric='logloss', scale_pos_weight=max(1.0, neg / max(1.0, pos)), **common)
        return XGBRegressor(objective='reg:squarederror', **common)
    raise ValueError(f'Unknown estimator: {name}')


def predict_values(estimator, features: np.ndarray, classification: bool):
    pred = estimator.predict(features)
    if classification:
        classes = getattr(estimator, 'classes_', None)
        ensure(classes is not None and set(np.asarray(classes).tolist()).issubset({0, 1}), 'Invalid binary output classes')
        pred = np.asarray(pred, dtype=int)
        ensure(np.isin(pred, [0, 1]).all(), 'Non-binary class predictions')
    else:
        pred = np.clip(np.asarray(pred, dtype=float), 0, 100)
    return pred


def metrics_by_disease(frame: pd.DataFrame, target: str, predictions, classification: bool):
    true = frame[target].to_numpy()
    predictions = np.asarray(predictions)
    output = []
    for disease in DISEASES:
        mask = frame.Disease_Name.eq(disease).to_numpy()
        actual, pred = true[mask], predictions[mask]
        ensure(len(actual) > 0, f'No evaluation rows for {disease}')
        if classification:
            record = {'f1_macro': float(f1_score(actual, pred, labels=[0, 1], average='macro', zero_division=0)),
                      'f1_positive': float(f1_score(actual, pred, pos_label=1, zero_division=0)),
                      'precision_positive': float(precision_score(actual, pred, zero_division=0)),
                      'recall_positive': float(recall_score(actual, pred, zero_division=0)),
                      'accuracy': float(accuracy_score(actual, pred)),
                      'positive_prevalence': float(np.mean(actual))}
        else:
            record = {'mae': float(mean_absolute_error(actual, pred)),
                      'rmse': float(np.sqrt(mean_squared_error(actual, pred)))}
        output.append({'disease': disease, 'rows': int(mask.sum()), **record})
    score_name = 'f1_macro' if classification else 'mae'
    selected_score = float(np.mean([r[score_name] for r in output]))  # equal disease weight
    return output, selected_score


def train(root: Path, mode: str, models: list[str], jobs: int, seed: int):
    ensure(mode in {'smoke', 'full'}, 'Mode must be smoke or full')
    ensure(models and len(models) == len(set(models)), 'Empty/repeated model choices')
    ensure(set(models).issubset({'rf', 'lgbm', 'xgb'}), 'Supported models: rf,lgbm,xgb')
    ensure(1 <= jobs <= 16, 'Use jobs between 1 and 16')
    features, targets = load_contract(root)
    train_df = load_split(root, 'train', features, targets)
    val_df = load_split(root, 'validation', features, targets)
    # test remains UNREAD in smoke mode, and is delayed until AFTER model selection in full.
    if mode == 'smoke':
        train_df = limit_for_smoke(train_df, 1600, seed)
        val_df = limit_for_smoke(val_df, 600, seed + 41)
        targets = [f'Target_{kind}_Day_{day}' for day in (1, 7)
                   for kind in ('Disease_Active', 'Incidence_Pct', 'New_Onset_By')]
    ensure(train_df.Forecast_Origin_Date.max() < val_df.Forecast_Origin_Date.min() or mode == 'smoke',
           'Train/validation chronology not isolated')
    X_train = train_df[features].to_numpy(dtype=np.float32)
    X_val = val_df[features].to_numpy(dtype=np.float32)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    run_dir = root / 'models' / 'spread' / 'multidisease_step28' / f'{mode}_{stamp}'
    out_dir = root / 'outputs' / 'reports' / 'multidisease_step28' / f'{mode}_{stamp}'
    run_dir.mkdir(parents=True, exist_ok=False)
    out_dir.mkdir(parents=True, exist_ok=False)
    comparisons = []
    choices = []
    kept_models = {}
    print('=' * 76, flush=True)
    print(f'STEP 28 - 4-DISEASE CSV BASELINE | {mode.upper()} | TRAIN + VALIDATION', flush=True)
    print('=' * 76, flush=True)
    print(f'Models={models}; features={len(features)}; train={len(train_df)}; validation={len(val_df)}', flush=True)
    for index, target in enumerate(targets, 1):
        binary = 'Incidence_Pct' not in target
        actual_train = train_df[target].to_numpy(dtype=np.int32 if binary else np.float32)
        ensure(not binary or np.isin(actual_train, [0, 1]).all(), f'Invalid binary labels {target}')
        best = None
        for model_name in models:
            # If training contains one binary class, a majority-only DummyClassifier
            # is safer than crashing; flag the limitation explicitly.
            if binary and np.unique(actual_train).size < 2:
                from sklearn.dummy import DummyClassifier
                fitted = DummyClassifier(strategy='most_frequent').fit(X_train, actual_train)
                fallback = True
            else:
                fitted = make_estimator(model_name, binary, jobs, seed, mode == 'smoke', actual_train)
                fitted.fit(X_train, actual_train)
                fallback = False
            predicted = predict_values(fitted, X_val, binary)
            rows, score = metrics_by_disease(val_df, target, predicted, binary)
            comparisons.append({'target': target, 'model': model_name, 'validation_score': score,
                                'validation_metric': 'mean_disease_macro_f1' if binary else 'mean_disease_mae',
                                'fallback_constant_label': fallback})
            better = best is None or ((score > best['score'] + 1e-10) if binary
                                      else (score < best['score'] - 1e-10))
            if better:
                best = {'name': model_name, 'score': score, 'estimator': fitted,
                        'per_disease': rows, 'fallback_constant_label': fallback}
        ensure(best is not None, f'No model selected for {target}')
        ckpt = f'{target}__{best["name"]}.joblib'
        joblib.dump(best['estimator'], run_dir / ckpt)
        kept_models[target] = best['estimator']
        choices.append({'target': target, 'best_model': best['name'], 'checkpoint': ckpt,
                        'task': 'classification' if binary else 'regression',
                        'validation_score': best['score'],
                        'validation_metric': 'mean_disease_macro_f1' if binary else 'mean_disease_mae',
                        'validation_per_disease': best['per_disease'],
                        'fallback_constant_label': best['fallback_constant_label']})
        print(f'[{index:02d}/{len(targets)}] {target:36} best={best["name"]:4} '
              f'val={best["score"]:.4f} ({"macro F1" if binary else "MAE"})', flush=True)

    pd.DataFrame(comparisons).to_csv(out_dir / 'validation_model_comparison.csv', index=False)
    test_aggregate = []
    test_rows = []
    if mode == 'full':
        print('All 21 validation winners selected. Reading held-out TEST ONCE for reporting...', flush=True)
        test_df = load_split(root, 'test', features, targets)
        ensure(train_df.Forecast_Origin_Date.max() < val_df.Forecast_Origin_Date.min() < test_df.Forecast_Origin_Date.min(),
               'Chronological train/val/test order invalid')
        test_features = test_df[features].to_numpy(dtype=np.float32)
        for choice in choices:
            target = choice['target']
            binary = choice['task'] == 'classification'
            prediction = predict_values(kept_models[target], test_features, binary)
            by_disease, score = metrics_by_disease(test_df, target, prediction, binary)
            test_aggregate.append({'target': target, 'best_model': choice['best_model'],
                                   'test_score': score, 'metric': choice['validation_metric']})
            test_rows.extend([{'target': target, 'best_model': choice['best_model'], **row}
                              for row in by_disease])
        pd.DataFrame(test_aggregate).to_csv(out_dir / 'heldout_test_summary.csv', index=False)
        pd.DataFrame(test_rows).to_csv(out_dir / 'heldout_test_per_disease.csv', index=False)
    else:
        ensure(len(choices) == 6, 'Smoke mode must run six target checks')
    manifest = {
        'schema_version': 'step28-v1', 'mode': mode,
        'ready_for_inference': mode == 'full', 'training_scope': 'SYNTHETIC 16 BLOCK / 4 DISEASE',
        'scientific_evaluation': 'Simulation fit ONLY, NO real plantation validation',
        'models_compared': models, 'feature_columns': features,
        'feature_contract': 'data/processed/multidisease_feature_contract.json',
        'required_preprocessing': ['multidisease_train_fitted_preprocessor.joblib',
                                   'multidisease_step26_feature_pipeline.joblib'],
        'input_contract': '48 precomputed Step26 columns in exact feature order; do NOT supply raw weather or future target columns',
        'disease_names': DISEASES, 'targets': [r['target'] for r in choices],
        'chosen': choices, 'evaluation_policy': 'Validation selects model; test used ONCE after selections in full mode',
        'test_evaluated': mode == 'full', 'model_directory': str(run_dir),
        'report_directory': str(out_dir), 'model_count': len(choices), 'random_seed': seed,
    }
    save_json(run_dir / 'manifest.json', manifest)
    save_json(out_dir / 'run_summary.json', {'mode': mode, 'rows_train': len(train_df),
             'rows_validation': len(val_df), 'test_evaluated': mode == 'full',
             'models_compared': models, 'models_saved': len(choices),
             'run_dir': str(run_dir), 'note': 'ALL DATA SYNTHETIC'})
    if mode == 'full':
        save_json(root / 'models' / 'spread' / 'multidisease_step28' / 'latest_full.json',
                  {'manifest_relative_path': f'{run_dir.name}/manifest.json',
                   'run_directory_name': run_dir.name, 'schema_version': 'step28-v1'})
    print(f'PASS: {len(choices)} saved winners; TEST evaluated={mode == "full"}', flush=True)
    print(f'Models: {run_dir}', flush=True)
    print(f'Reports: {out_dir}', flush=True)
    print('WARNING: synthetic outcomes, dummy block graph, climate location unverified.', flush=True)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['smoke', 'full'], default='smoke')
    parser.add_argument('--models', default='rf', help='Comma list: rf,lgbm,xgb')
    parser.add_argument('--jobs', type=int, default=2)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--component-root', type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    train(args.component_root.resolve(), args.mode,
          [x.strip().lower() for x in args.models.split(',') if x.strip()], args.jobs, args.seed)

if __name__ == '__main__':
    main()
