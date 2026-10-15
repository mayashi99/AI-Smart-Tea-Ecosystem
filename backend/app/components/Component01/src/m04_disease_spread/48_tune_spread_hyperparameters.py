"""Step 48: train-only chronological hyperparameter tuning (simulation only).

DOES NOT open any test.csv, change existing Step 28/31 selected models, or deploy.
Input: Step26 engineered 48 features; synthetic four-disease pooled task heads.
Tuning: embargoed chronological folds WITHIN train; final 2025 validation is
scored once for reporting. All held-out test data remain unaccessed.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import (accuracy_score, f1_score, mean_absolute_error,
                             precision_score, recall_score)

DISEASES = ['Brown Blight', 'Grey Leaf', 'Red Rust', 'Red Spider Mite']
KINDS = ('Disease_Active', 'Incidence_Pct', 'New_Onset_By')
KEYS = ['Forecast_Origin_Date', 'Estate_ID', 'Block_ID', 'Disease_Name']
META = KEYS + ['Split']


def ensure(ok, message):
    if not ok:
        raise ValueError(message)


def dump_json(path, item):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(item, indent=2, default=str, allow_nan=False) + '\n', encoding='utf-8')


def target_set(mode):
    all_targets = [f'Target_{kind}_Day_{d}' for d in range(1, 8) for kind in KINDS]
    if mode == 'quick':
        names = [f'Target_{kind}_Day_1' for kind in KINDS] + ['Target_Disease_Active_Day_7']
    elif mode == 'focused':
        names = [f'Target_{kind}_Day_{d}' for d in (1, 7) for kind in KINDS]
    elif mode == 'all':
        names = all_targets
    else:
        raise ValueError('mode must be quick, focused or all')
    ensure(len(set(names)) == len(names), 'Duplicate target')
    return names


def verify_contract(root):
    file = root / 'data/processed/multidisease_feature_contract.json'
    ensure(file.is_file(), f'Missing Step26 contract: {file}')
    contract = json.loads(file.read_text(encoding='utf-8'))
    cols = list(contract['feature_columns'])
    targets = list(contract['target_columns'])
    expected = [f'Target_{kind}_Day_{d}' for d in range(1, 8) for kind in KINDS]
    ensure(len(cols) == 48 and len(set(cols)) == 48, 'Step26 48-column schema required')
    ensure(targets == expected, 'Step26 target order unexpectedly changed')
    ensure(not set(cols).intersection(targets), 'Target leakage: features overlap labels')
    ensure(not any(name.startswith('Target_') for name in cols), 'Future-target feature leakage')
    ensure(set(contract['disease_names']) == set(DISEASES), 'Disease mapping mismatch')
    ensure(len(contract.get('added_past_only_features', [])) == 20,
           'Step26 past-only 20 lag and rolling features contract required')
    return cols, targets


def load_limited_split(root, split, features, targets):
    ensure(split in {'train', 'validation'}, 'Forbidden split: NEVER read test for tuning')
    file = root / 'data/processed' / f'multidisease_features_{split}.csv'
    ensure(file.is_file(), f'Missing file: {file}')
    table = pd.read_csv(file, usecols=META + features + targets, low_memory=False)
    ensure(len(table) > 0 and table.Split.eq(split).all(), f'Invalid {split} split')
    ensure(not table.duplicated(KEYS).any(), f'Duplicate {split} keys')
    ensure(set(table.Disease_Name) == set(DISEASES), f'Missing disease in {split}')
    ensure(table.Block_ID.nunique() == 16, f'Expected 16 blocks in {split}')
    dates = pd.to_datetime(table.Forecast_Origin_Date, errors='raise')
    ensure(dates.notna().all(), f'Missing dates in {split}')
    arr = table[features + targets].to_numpy(dtype=np.float64)
    ensure(np.isfinite(arr).all(), f'Nonfinite features or labels in {split}')
    for t in targets:
        if 'Incidence_Pct' not in t:
            ensure(table[t].isin([0, 1]).all(), f'Invalid binary labels: {t}')
        else:
            ensure(table[t].between(0, 100).all(), f'Invalid incidence labels: {t}')
    return table, dates


def inner_folds(dates, count, embargo_days=7):
    """Block by shared origin date, purge past 7-day target overlap."""
    ensure(count in (1, 2), 'Fold count must be 1 or 2')
    unique = sorted(pd.to_datetime(dates.unique()))
    ensure(len(unique) >= 60, 'Insufficient chronology for inner tuning')
    fractions = [(0.78, 1.0)] if count == 1 else [(0.55, 0.75), (0.78, 1.0)]
    results = []
    for i, (start, end) in enumerate(fractions, 1):
        start_idx = int(len(unique)*start)
        end_idx = min(len(unique), max(start_idx + 1, int(len(unique)*end)))
        begin = unique[start_idx]
        finish = unique[end_idx-1]
        train_before = begin - pd.Timedelta(days=embargo_days)
        train_idx = np.flatnonzero(dates < train_before)
        val_idx = np.flatnonzero((dates >= begin) & (dates <= finish))
        ensure(train_idx.size > 0 and val_idx.size > 0, 'Empty fold')
        ensure(len(pd.unique(dates.iloc[train_idx])) >= 25, 'Insufficient inner train dates')
        ensure(len(pd.unique(dates.iloc[val_idx])) >= 10, 'Insufficient inner validation dates')
        ensure(dates.iloc[train_idx].max() + pd.Timedelta(days=embargo_days) < dates.iloc[val_idx].min(),
               'Target-horizon overlap risk in inner folds')
        results.append((i, train_idx, val_idx, str(begin.date()), str(finish.date())))
    return results


def configurations(model):
    # Small, reproducible, CPU-aware search; configs are not a claim of global optimization.
    if model == 'rf':
        return [
            {'n_estimators': 60, 'max_depth': 12, 'min_samples_leaf': 4, 'max_features': 'sqrt'},
            {'n_estimators': 100, 'max_depth': 18, 'min_samples_leaf': 2, 'max_features': 'sqrt'},
        ]
    if model == 'lgbm':
        return [
            {'n_estimators': 80, 'learning_rate': 0.05, 'num_leaves': 15, 'min_child_samples': 30},
            {'n_estimators': 120, 'learning_rate': 0.06, 'num_leaves': 31, 'min_child_samples': 20},
        ]
    if model == 'xgb':
        return [
            {'n_estimators': 80, 'learning_rate': 0.05, 'max_depth': 4, 'min_child_weight': 3},
            {'n_estimators': 120, 'learning_rate': 0.06, 'max_depth': 6, 'min_child_weight': 5},
        ]
    raise ValueError(f'Invalid model name {model}')


def make_model(name, params, classification, y, seed, jobs):
    if classification and len(np.unique(y)) < 2:
        return DummyClassifier(strategy='most_frequent')
    if name == 'rf':
        args = dict(params, random_state=seed, n_jobs=jobs)
        return (RandomForestClassifier(class_weight='balanced_subsample', **args)
                if classification else RandomForestRegressor(**args))
    if name == 'lgbm':
        import lightgbm as lgb
        args = dict(params, random_state=seed, n_jobs=jobs, verbosity=-1)
        return (lgb.LGBMClassifier(class_weight='balanced', **args)
                if classification else lgb.LGBMRegressor(**args))
    if name == 'xgb':
        from xgboost import XGBClassifier, XGBRegressor
        args = dict(params, random_state=seed, n_jobs=jobs, subsample=0.9,
                    colsample_bytree=0.9, tree_method='hist')
        if classification:
            pos = max(1.0, float(np.sum(y == 1)))
            neg = float(np.sum(y == 0))
            return XGBClassifier(eval_metric='logloss',
                                 scale_pos_weight=max(1.0, neg/pos), **args)
        return XGBRegressor(objective='reg:squarederror', **args)
    raise ValueError(name)


def predict(model, X, classification):
    # Estimator trained on NumPy features; maintain the same 48-column order.
    if model.__class__.__module__.startswith('lightgbm'):
        names = getattr(model, 'feature_names_in_', None)
        if names is not None and len(names) == X.shape[1]:
            X = pd.DataFrame(X, columns=list(names))
    values = np.asarray(model.predict(X))
    if classification:
        ensure(np.isin(values, [0, 1]).all(), 'Non-binary classifier predictions')
        return values.astype(int)
    values = np.clip(values.astype(float), 0, 100)
    ensure(np.isfinite(values).all(), 'Nonfinite regression output')
    return values


def evaluate(data, disease_col, target, preds, classification):
    result = []
    truth = np.asarray(data[target])
    diseases = np.asarray(disease_col)
    for disease in DISEASES:
        mask = diseases == disease
        ensure(mask.any(), 'Empty disease evaluation group')
        yt, yp = truth[mask], np.asarray(preds)[mask]
        if classification:
            item = {'f1_macro': float(f1_score(yt, yp, labels=[0, 1], average='macro', zero_division=0)),
                    'f1_positive': float(f1_score(yt, yp, pos_label=1, zero_division=0)),
                    'positive_precision': float(precision_score(yt, yp, zero_division=0)),
                    'positive_recall': float(recall_score(yt, yp, zero_division=0)),
                    'accuracy': float(accuracy_score(yt, yp)),
                    'prevalence': float(np.mean(yt))}
        else:
            item = {'mae': float(mean_absolute_error(yt, yp))}
        result.append({'disease': disease, 'rows': int(mask.sum()), **item})
    metric = 'f1_macro' if classification else 'mae'
    return float(np.mean([r[metric] for r in result])), result


def run(root, mode, models, folds, jobs, seed):
    root = root.resolve()
    ensure(models and set(models).issubset({'rf','lgbm','xgb'}), 'Models must be rf,lgbm,xgb')
    ensure(1 <= jobs <= 8, 'jobs must be between 1 and 8')
    targets = target_set(mode)
    features, all_targets = verify_contract(root)
    train, train_dates = load_limited_split(root, 'train', features, targets)
    val, val_dates = load_limited_split(root, 'validation', features, targets)
    ensure(train_dates.max() + pd.Timedelta(days=7) < val_dates.min(),
           'Train/validation 7-day target embargo missing')
    fold_list = inner_folds(train_dates, folds)
    x_train = train[features].to_numpy(dtype=np.float32)
    x_val = val[features].to_numpy(dtype=np.float32)
    train_dis = train.Disease_Name.to_numpy()
    val_dis = val.Disease_Name.to_numpy()

    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    model_dir = root / 'models/spread/multidisease_step48' / f'{mode}_{stamp}'
    report_dir = root / 'outputs/reports/multidisease_step48' / f'{mode}_{stamp}'
    ensure(not model_dir.exists() and not report_dir.exists(), 'Run ID collision')
    model_dir.mkdir(parents=True)
    report_dir.mkdir(parents=True)
    candidates = []
    selections = []
    started = time.monotonic()
    print('='*82, flush=True)
    print(f'STEP 48 - LEAKAGE-AWARE HYPERPARAMETER EXPERIMENT | {mode.upper()}', flush=True)
    print('='*82, flush=True)
    print(f'Train rows={len(train):,} dates={train_dates.nunique()} | validation rows={len(val):,} | features=48',flush=True)
    print(f'Targets={len(targets)}, algorithms={models}, configs/algorithm=2, inner chronological folds={folds}',flush=True)
    print('7-day embargo in INNER folds; TEST FILE NOT READ; Step 28/31 deployments untouched.',flush=True)
    for idx, target in enumerate(targets,1):
        binary = 'Incidence_Pct' not in target
        y_train = train[target].to_numpy(dtype=np.int32 if binary else np.float32)
        scored = []
        for model_name in models:
            for config_id, cfg in enumerate(configurations(model_name), 1):
                fold_scores = []
                for fid, fit_idx, eval_idx, first_date, last_date in fold_list:
                    estimator = make_model(model_name, cfg, binary, y_train[fit_idx], seed, jobs)
                    estimator.fit(x_train[fit_idx], y_train[fit_idx])
                    prediction = predict(estimator, x_train[eval_idx], binary)
                    score, by_dis = evaluate(train.iloc[eval_idx], train_dis[eval_idx], target,
                                             prediction, binary)
                    fold_scores.append(score)
                    candidates.append(dict(target=target, model=model_name, config_id=config_id,
                                            fold=fid, metric='mean_disease_macro_f1' if binary else 'mean_disease_mae',
                                            inner_score=score, inner_first_date=first_date,
                                            inner_last_date=last_date, train_rows=len(fit_idx),
                                            inner_validation_rows=len(eval_idx), parameters=json.dumps(cfg,sort_keys=True)))
                scored.append((float(np.mean(fold_scores)), model_name, config_id, cfg))
                print(f'  [{idx}/{len(targets)}] {target} {model_name} cfg={config_id}: inner={np.mean(fold_scores):.5f}',flush=True)
        ordered = sorted(scored, key=lambda x: ((-x[0] if binary else x[0]), x[1], x[2]))
        inner_score, best_name, best_id, best_cfg = ordered[0]
        best_model = make_model(best_name, best_cfg, binary, y_train, seed, jobs)
        best_model.fit(x_train, y_train)
        preds = predict(best_model, x_val, binary)
        outer_score, by_dis = evaluate(val, val_dis, target, preds, binary)
        file = f'{target}__{best_name}_cfg{best_id}.joblib'
        joblib.dump(best_model, model_dir / file)
        entry = dict(target=target, task='classification' if binary else 'regression',
                     metric='mean_disease_macro_f1' if binary else 'mean_disease_mae',
                     model=best_name, config_id=best_id, parameters=best_cfg,
                     inner_cv_score=inner_score, validation_2025_score=outer_score,
                     validation_2025_per_disease=by_dis, checkpoint=file,
                     positive_detection_caution=('Inspect positive recall; macro F1 alone can hide missed onsets' if 'New_Onset' in target else ''))
        selections.append(entry)
        print(f'  SELECT [{idx}/{len(targets)}] {target}: {best_name}/cfg{best_id} '
              f'inner={inner_score:.5f}, 2025 validation={outer_score:.5f}',flush=True)
    pd.DataFrame(candidates).to_csv(report_dir/'inner_cv_trials.csv', index=False)
    rows = [dict(target=r['target'], model=r['model'], parameters=json.dumps(r['parameters'], sort_keys=True),
                 metric=r['metric'], inner_cv_score=r['inner_cv_score'],
                 validation_2025_score=r['validation_2025_score'], checkpoint=r['checkpoint'])
            for r in selections]
    pd.DataFrame(rows).to_csv(report_dir/'validation_tuned_summary.csv', index=False)
    info = dict(schema_version='step48-tuning-experiment-v1', status='PASS_EXPLORATORY_TUNING',
                mode=mode, models_tried=models, split_policy='TRAIN-only inner chronological folds +7-day embargo; external validation report only',
                training_dates=f'{train_dates.min().date()} .. {train_dates.max().date()}',
                external_validation_dates=f'{val_dates.min().date()} .. {val_dates.max().date()}',
                folds=[dict(fold=i, train_rows=len(tr), inner_val_rows=len(iv),
                            first_inner_val=sd, last_inner_val=ed)
                       for i,tr,iv,sd,ed in fold_list],
                feature_columns=features, disease_names=DISEASES, target_count=len(targets),
                train_rows=len(train), validation_rows=len(val), targets=selections,
                trained_checkpoints_saved=True, test_opened=False,
                automatically_promoted_to_step31_or_step42=False,
                clinical_or_field_validation=False,
                notes=['Synthetic plantation blocks and outcomes; NASA climate point unverified for estate',
                       'Tuned candidates EXPLORATORY; previous 2025 validation has already been used for model-family selection',
                       'Use a fresh independent field holdout before making deployment improvement claims',
                       'Do not alter Step28 latest_full, Step31 family registry, Step42/45 API or runtime records'],
                runtime_seconds=round(time.monotonic()-started,2),
                model_dir=str(model_dir), report_dir=str(report_dir))
    dump_json(model_dir/'experimental_registry.json', info)
    dump_json(report_dir/'tuning_audit.json', info)
    print('='*82, flush=True)
    print(f'PASS: {len(targets)} tuned candidate models saved separately; TEST NEVER OPENED.', flush=True)
    print(f'Models: {model_dir}', flush=True)
    print(f'Report: {report_dir}', flush=True)
    print('NOT promoted to existing API. No claim of real-world accuracy or new independent test.', flush=True)
    return info


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode', choices=['quick','focused','all'],default='quick',
                   help='quick=4 heads; focused=Day1/7 six heads; all=21 heads (can be very slow)')
    p.add_argument('--models',default='rf,lgbm',
                   help='Comma-separated candidates rf,lgbm,xgb. Default 2 for i7 CPU.')
    p.add_argument('--folds',type=int,default=1, choices=[1,2])
    p.add_argument('--jobs',type=int,default=2)
    p.add_argument('--seed',type=int,default=42)
    p.add_argument('--component-root',type=Path,default=Path(__file__).resolve().parents[2])
    a = p.parse_args()
    names = [x.strip().lower() for x in a.models.split(',') if x.strip()]
    ensure(len(names) == len(set(names)), 'Duplicate model choice')
    run(a.component_root, a.mode, names, a.folds, a.jobs, a.seed)

if __name__ == '__main__':
    main()
