"""Step 31: validation-only fair model comparison for 4-disease synthetic spread.

Runs the saved Step 28 tabular 21-target winners, Step 29 per-block LSTM,
and Step 30 GCN-LSTM on precisely the SAME 14-day-history-eligible
validation origins / diseases / blocks. No held-out test data are loaded.

Model selection on previously used validation data is exploratory. Test metrics
from Step 28 MUST NOT be reused for this cross-family model selection.
Data source: SIMULATION_ONLY; dummy 16-block graph; not field validated.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, mean_absolute_error
import torch

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from multidisease_lstm_inference import decode_predictions, load_lstm
from multidisease_gcn_lstm_inference import decode_graph_outputs, load_gcn_lstm

KINDS = ('Disease_Active', 'Incidence_Pct', 'New_Onset_By')
DISPLAY_METRICS = ('activity_macro_f1', 'incidence_mae', 'new_onset_macro_f1')
MODEL_NAMES = ('ml_winners', 'lstm', 'gcn_lstm')


def require(cond, message):
    if not cond:
        raise RuntimeError(message)


def read_json(p):
    require(p.is_file(), f'Missing file: {p}')
    return json.loads(p.read_text(encoding='utf-8'))


def latest_full_run(root, step):
    parent = root / 'models' / 'spread' / f'multidisease_step{step}'
    candidates = sorted((p for p in parent.glob('full_*') if (p / 'manifest.json').is_file()),
                        key=lambda p: p.name)
    require(candidates, f'No Step {step} FULL training run in {parent}')
    return candidates[-1]


def choose_step28(root):
    parent = root / 'models/spread/multidisease_step28'
    latest = parent / 'latest_full.json'
    if latest.exists():
        ptr = read_json(latest)
        name = ptr.get('run_directory_name')
        if name and (parent / name / 'manifest.json').exists():
            return parent / name
    return latest_full_run(root, 28)


def load_validation(root, limit_origins):
    proc = root / 'data/processed'
    seq_contract = read_json(proc / 'multidisease_sequence_graph_contract.json')
    features = list(seq_contract['input_feature_columns'])
    disease_names = list(seq_contract['disease_names'])
    block_ids = list(seq_contract['block_ids'])
    require(len(features) == 48 and len(set(features)) == 48, 'Expected 48 features')
    require(len(disease_names) == 4 and len(block_ids) == 16, 'Expected 4 diseases, 16 blocks')
    require(not any(f.startswith('Target_') for f in features), 'Future target in predictors!')
    with np.load(proc / 'multidisease_sequence_graph_validation.npz', allow_pickle=False) as src:
        arrays = {k: src[k] for k in ('X_days', 'Y_days', 'dates', 'sample_indices')}
    idx = arrays['sample_indices'].astype(int)
    dates = arrays['dates'].astype(str)
    length = int(seq_contract['sequence_days'])
    require(length == 14 and idx.shape[1] == 2, 'Expected 14-day Step27 sequence indexes')
    require(arrays['X_days'].shape[1:] == (4,16,48), 'X_days shape/ordering changed')
    require(arrays['Y_days'].shape[1:] == (4,16,7,3), 'Y_days shape/ordering changed')
    if limit_origins:
        # deterministic smallest first interval, not random mix; smoke is NOT selection-grade
        eligible = np.unique(idx[:,0]); chosen = set(eligible[:limit_origins].tolist())
        idx = idx[np.isin(idx[:,0], list(chosen))]
    require(len(idx)>0, 'No validation samples found')
    origin = [str(dates[end]) for end,_ in idx]
    dis = [disease_names[dis_id] for _,dis_id in idx]
    labels = arrays['Y_days'][idx[:,0], idx[:,1]]  # [n_graph_samples,16,7,3]
    expected_keys = [(day, disease, block) for day,disease in zip(origin,dis) for block in block_ids]
    feature_contract = read_json(proc / 'multidisease_feature_contract.json')
    require(list(feature_contract['feature_columns']) == features, 'Step 26/27 feature mismatch')
    required = ['Forecast_Origin_Date','Disease_Name','Block_ID','Split'] + features + [
        f'Target_{kind}_Day_{day}' for day in range(1,8) for kind in KINDS]
    table = pd.read_csv(proc / 'multidisease_features_validation.csv', usecols=required,
                        low_memory=False)
    require(table.Split.eq('validation').all(), 'Split mismatch!')
    require(not table.duplicated(['Forecast_Origin_Date','Disease_Name','Block_ID']).any(), 'Duplicate validation row key')
    table = table.set_index(['Forecast_Origin_Date','Disease_Name','Block_ID'])
    keys = pd.MultiIndex.from_tuples(expected_keys, names=table.index.names)
    selected = table.reindex(keys)
    require(selected[features].notna().all().all(), 'Some aligned validation feature rows missing')
    x_tabular = selected[features].to_numpy(dtype=np.float32)
    true_tabular = selected[[f'Target_{kind}_Day_{day}' for day in range(1,8)
                             for kind in KINDS]].to_numpy(dtype=np.float32).reshape(-1,16,7,3)
    require(np.allclose(true_tabular, labels, atol=1e-4), 'Step 26 / Step 27 aligned target mismatch')
    require(np.isfinite(x_tabular).all(), 'Nonfinite selected ML features')
    return dict(arrays=arrays, indices=idx, origin=origin, diseases=dis, block_ids=block_ids,
                labels=labels, x_tabular=x_tabular, features=features,
                disease_names=disease_names, seq_contract=seq_contract)


def predict_ml(root, dataset, run):
    m = read_json(run / 'manifest.json')
    require(m.get('mode')=='full' and m.get('model_count')==21, 'Expected Step28 21 full fitted winners')
    require(m['feature_columns']==dataset['features'], 'Step 28 feature order mismatch')
    require(m['disease_names']==dataset['disease_names'], 'Step 28 disease order mismatch')
    require(set(m['targets'])==set(f'Target_{kind}_Day_{day}' for day in range(1,8)
                                   for kind in KINDS), 'Step28 target set mismatch')
    choices = {c['target']: c for c in m['chosen']}
    n = len(dataset['indices'])
    out = np.zeros((n*16,7,3), dtype=np.float32)
    selected_algos = {}
    for day in range(1,8):
        for j,kind in enumerate(KINDS):
            target=f'Target_{kind}_Day_{day}'
            chosen = choices[target]
            model_file = run / chosen['checkpoint']
            require(model_file.is_file(), f'No ML checkpoint {model_file}')
            fitted = joblib.load(model_file)
            # Step28 trains on NumPy arrays. LightGBM may attach synthetic
            # Column_0...Column_47 names; retain the SAME numeric column order.
            model_input = dataset['x_tabular']
            if fitted.__class__.__module__.startswith('lightgbm'):
                raw_names = getattr(fitted, 'feature_names_in_', None)
                names = [str(x) for x in raw_names] if raw_names is not None else []
                if len(names) == len(dataset['features']):
                    model_input = pd.DataFrame(model_input, columns=names)
            predictions = np.asarray(fitted.predict(model_input), dtype=np.float32)
            require(predictions.shape == (n*16,), f'Invalid ML prediction for {target}')
            if j!=1:
                require(np.isin(predictions,[0,1]).all(), f'Invalid binary ML predictions for {target}')
            else:
                predictions = np.clip(predictions,0,100)
            out[:,day-1,j] = predictions
            selected_algos[target] = chosen['best_model']
    return out.reshape(n,16,7,3), selected_algos


def predict_lstm(dataset, run, batch_size, threads):
    model, manifest=load_lstm(run,device='cpu')
    require(manifest['disease_names']==dataset['disease_names'], 'LSTM disease order mismatch')
    require(manifest['block_ids']==dataset['block_ids'], 'LSTM block order mismatch')
    require(manifest['lookback_days']==14 and manifest['feature_count']==48,'LSTM input mismatch')
    torch.set_num_threads(threads)
    x_days=dataset['arrays']['X_days']
    indices=dataset['indices']
    out=[]
    with torch.inference_mode():
        for lo in range(0,len(indices),batch_size):
            batch=[]
            for end,disease_id in indices[lo:lo+batch_size]:
                # [T, B, F] -> [B, T, F] -- one sample per block
                history=x_days[end-13:end+1,disease_id].transpose(1,0,2)
                batch.append(history)
            z=np.concatenate(batch,axis=0)
            decoded=decode_predictions(model(torch.from_numpy(np.ascontiguousarray(z))))
            out.append(decoded.cpu().numpy().reshape(-1,16,7,3))
    return np.concatenate(out,axis=0)


def predict_gcn(root,dataset,run,batch_size,threads):
    model,adj,manifest=load_gcn_lstm(run, component_root=root,device='cpu')
    require(manifest['disease_names']==dataset['disease_names'], 'GCN disease order mismatch')
    require(manifest['block_ids']==dataset['block_ids'], 'GCN block order mismatch')
    require(manifest['lookback_days']==14, 'GCN lookback mismatch')
    torch.set_num_threads(threads)
    x_days=dataset['arrays']['X_days']; indices=dataset['indices']
    out=[]
    with torch.inference_mode():
        for lo in range(0,len(indices),batch_size):
            batch=np.stack([x_days[end-13:end+1,disease_id]
                            for end,disease_id in indices[lo:lo+batch_size]],axis=0)
            decoded=decode_graph_outputs(model(torch.from_numpy(np.ascontiguousarray(batch)),adj))
            out.append(decoded.cpu().numpy())
    return np.concatenate(out,axis=0)


def evaluate(dataset, model_predictions):
    labels=dataset['labels']; dis=np.asarray(dataset['diseases']); rows=[]
    metric_for_kind=['activity_macro_f1','incidence_mae','new_onset_macro_f1']
    for model_name,pred in model_predictions.items():
        require(pred.shape==labels.shape, f'{model_name}: prediction mismatch {pred.shape} vs {labels.shape}')
        require(np.isfinite(pred).all(), f'{model_name} predicted NaNs')
        for disease in dataset['disease_names']:
            mask=dis==disease
            require(mask.any(), f'{disease} missing')
            for day in range(1,8):
                for j,metric in enumerate(metric_for_kind):
                    y=labels[mask,:,day-1,j].ravel()
                    p=pred[mask,:,day-1,j].ravel()
                    if j!=1:
                        y_int=y.astype(int)
                        pred_int=(p>=0.5).astype(int) if model_name!='ml_winners' else p.astype(int)
                        score=float(f1_score(y_int,pred_int,labels=[0,1],average='macro',zero_division=0))
                    else:
                        score=float(mean_absolute_error(y,p))
                    rows.append(dict(model=model_name,disease=disease,day=day,metric=metric,
                                     value=score,records=len(y)))
    detail=pd.DataFrame(rows)
    summary=detail.groupby(['model','day','metric'],as_index=False).agg(
        validation_score=('value','mean'), disease_count=('disease','nunique'),
        validation_records=('records','sum'))
    require(summary.disease_count.eq(4).all(), 'Not all diseases evaluated')
    winner_rows=[]
    for (day,metric), part in summary.groupby(['day','metric']):
        ordered=part.sort_values(['validation_score','model'],ascending=[metric=='incidence_mae',True])
        top=ordered.iloc[0]
        target_kind={'activity_macro_f1':'Disease_Active','incidence_mae':'Incidence_Pct',
                     'new_onset_macro_f1':'New_Onset_By'}[metric]
        winner_rows.append(dict(target=f'Target_{target_kind}_Day_{day}',day=int(day),
                                metric=metric, selected_family=str(top.model),
                                validation_score=float(top.validation_score),
                                evaluation_origin_count=len(np.unique(dataset['indices'][:,0])),
                                notes='SYNTHETIC; validation-only exploratory model selection'))
    choices=pd.DataFrame(winner_rows).sort_values(['day','target']).reset_index(drop=True)
    require(len(choices)==21, 'Expected one selected family per day x target kind')
    return detail, summary, choices


def run(root, mode, max_origins, threads, batch_size):
    require(mode in {'smoke','full'}, 'Invalid mode')
    require(1<=threads<=16 and 1<=batch_size<=256, 'Invalid batch/threads')
    if mode=='full':
        require(max_origins is None, 'Full mode must compare ALL eligible validation origins')
    else:
        max_origins = max_origins or 2
        require(1<=max_origins<=30, 'Smoke mode can use 1-30 origins')
    root=root.resolve()
    p28=choose_step28(root); p29=latest_full_run(root,29); p30=latest_full_run(root,30)
    bundle=load_validation(root,max_origins)
    print('='*78,flush=True)
    print(f'STEP 31 - FAIR VALIDATION MODEL COMPARISON | {mode.upper()} | SIMULATION',flush=True)
    print('='*78,flush=True)
    print(f'Origin days={len(set(bundle["origin"]))}, graph windows={len(bundle["indices"])}, '
          f'block/disease records={len(bundle["indices"])*16}',flush=True)
    print(f'Input features={len(bundle["features"])} | target heads=3 | horizon=7',flush=True)
    print('All model families are evaluated on EXACTLY aligned validation records.',flush=True)
    print('Held-out TEST is NEVER loaded or used for Step31 selection.',flush=True)
    results={}
    print('  Loading 21 selected ML estimators...',flush=True)
    results['ml_winners'], algos=predict_ml(root,bundle,p28)
    print('  Running per-block LSTM validation inference...',flush=True)
    results['lstm']=predict_lstm(bundle,p29,batch_size,threads)
    print('  Running 16-node GCN-LSTM validation inference...',flush=True)
    results['gcn_lstm']=predict_gcn(root,bundle,p30,batch_size,threads)
    detail,summary,chosen=evaluate(bundle,results)
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    report=root / 'outputs/reports/multidisease_step31' / f'{mode}_{stamp}'
    report.mkdir(parents=True,exist_ok=False)
    detail.to_csv(report / 'validation_per_disease_model_comparison.csv',index=False)
    summary.to_csv(report / 'validation_family_comparison.csv',index=False)
    chosen.to_csv(report / 'validation_selected_families.csv',index=False)
    manifest={
        'schema_version':'step31-v1', 'mode':mode,
        'status':'PASS_VALIDATION_ALIGNED_COMPARISON' if mode=='full' else 'PASS_SMOKE_NOT_FOR_SELECTION',
        'data_provenance':'SIMULATION_ONLY_NOT_FIELD_VALIDATED',
        'real_world_validation':False,'test_dataset_accessed':False,
        'evaluation_note':'This is validation data ALSO used previously for hyperparameter/checkpoint selection. Comparison is exploratory, may be optimistic. Step28 test reports MUST NOT select Step31 family.',
        'evaluation_origin_days':len(set(bundle['origin'])),
        'evaluation_rows':len(bundle['indices'])*16,
        'scoring':'Binary: macro F1 labels=[0,1] at threshold 0.5; incidence: MAE percent points. Equal weight per disease.',
        'input_feature_count':len(bundle['features']),
        'family_runs':{'ml_winners':str(p28.relative_to(root)), 'lstm':str(p29.relative_to(root)),
                       'gcn_lstm':str(p30.relative_to(root))},
        'step28_selected_algorithms':algos,
        'selected_families':chosen.to_dict(orient='records'),
        'limitations':['Synthetic disease labels and dummy graph',
                       'Climate source coordinates not confirmed against actual estate',
                       'All selection on already-used validation; do not cite as unbiased final performance',
                       'Onset classification may be highly imbalanced; inspect prevalence and positive-class F1'],
        'reports':{k:str((report/k).relative_to(root)) for k in (
            'validation_per_disease_model_comparison.csv',
            'validation_family_comparison.csv','validation_selected_families.csv')},
    }
    (report/'step31_comparison_summary.json').write_text(json.dumps(manifest,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    if mode=='full':
        choice_dir=root / 'models/spread/multidisease_step31'; choice_dir.mkdir(parents=True,exist_ok=True)
        (choice_dir/'validation_selected_families.json').write_text(
            json.dumps(manifest,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print('WINNER FAMILIES BY VALIDATION (aggregate over 4 diseases):',flush=True)
    for r in chosen.to_dict(orient='records'):
        print(f'  {r["target"]:<34} {r["selected_family"]:<12} '
              f'{r["metric"]}={r["validation_score"]:.4f}',flush=True)
    print('PASS: 21 comparable family choices, simulation-only.',flush=True)
    print('Reports:',report,flush=True)
    print('No TEST data loaded. Interpret as VALIDATION selection, not final unbiased accuracy.',flush=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,default=HERE.parents[1])
    ap.add_argument('--mode',choices=['smoke','full'],default='smoke')
    ap.add_argument('--max-origins',type=int,default=None,
                    help='Only smoke: first N eligible validation origin days (max 30)')
    ap.add_argument('--batch-size',type=int,default=8)
    ap.add_argument('--threads',type=int,default=2)
    a=ap.parse_args()
    run(a.root,a.mode,a.max_origins,a.threads,a.batch_size)

if __name__=='__main__':
    main()
