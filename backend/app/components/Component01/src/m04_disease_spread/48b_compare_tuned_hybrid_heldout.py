"""Step 48B: one-time held-out synthetic TEST comparison of frozen Step31 hybrid
and a candidate hybrid with Step48 tuned ML substituted for Step31 ML heads.

Test is never used to tune or select. Original models and APIs are never touched.
2026 test was previously accessed by Step28 and thus is not a pristine new study holdout.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, f1_score, mean_absolute_error,
                             mean_squared_error, precision_score, recall_score,
                             confusion_matrix)

KINDS = ('Disease_Active', 'Incidence_Pct', 'New_Onset_By')
TARGETS = [f'Target_{kind}_Day_{day}' for day in range(1, 8) for kind in KINDS]
FAMILIES = {'ml_winners', 'lstm', 'gcn_lstm'}


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def read_json(path):
    require(path.is_file(), f'Missing required file: {path}')
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def within(root, fragment):
    path = (root / fragment).resolve()
    require(path.is_relative_to(root), f'Unsafe path outside component: {fragment}')
    return path


def load_step31(root):
    source = root / 'src/m04_disease_spread/31_compare_multidisease_models.py'
    require(source.is_file(), f'Missing Step31 code: {source}')
    folder = str(source.parent)
    if folder not in sys.path:
        sys.path.insert(0, folder)
    spec = importlib.util.spec_from_file_location('step31_frozen_comparison', source)
    require(spec is not None and spec.loader is not None, 'Cannot import Step31 helpers')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def preflight(root, tuned_run):
    root = root.resolve()
    tuned_run = tuned_run.resolve()
    require(tuned_run.parent == root / 'models/spread/multidisease_step48',
            f'Step48 run must be a direct child of {root / "models/spread/multidisease_step48"}')
    tuned_info = read_json(tuned_run / 'experimental_registry.json')
    require(tuned_info.get('status') == 'PASS_EXPLORATORY_TUNING' and tuned_info.get('mode') == 'all',
            'Requires verified Step48 ALL run, not quick or focused')
    require(tuned_info.get('target_count') == 21 and tuned_info.get('test_opened') is False,
            'Tuning registry not test-isolated/full')
    require(set(tuned_info.get('models_tried', [])) == {'rf', 'lgbm', 'xgb'},
            'Expected 3 algorithms from Step48 full experiment')
    choices48 = {x['target']: x for x in tuned_info['targets']}
    require(len(tuned_info['targets']) == 21 and set(choices48) == set(TARGETS),
            'Step48 registry must contain 21 unique targets')
    feature_contract = read_json(root / 'data/processed/multidisease_feature_contract.json')
    seq_contract = read_json(root / 'data/processed/multidisease_sequence_graph_contract.json')
    features = feature_contract['feature_columns']
    require(len(features) == 48 and len(set(features)) == 48 and
            seq_contract['input_feature_columns'] == features,
            'Step26/27 48-feature input order mismatch')
    require(feature_contract['target_columns'] == TARGETS and seq_contract['target_columns'] == TARGETS,
            'Step26/27 target order mismatch')
    require(tuned_info['feature_columns'] == features,
            'Step48 tuned models trained with different feature columns')
    require(set(seq_contract['disease_names']) == set(feature_contract['disease_names']) and
            len(seq_contract['disease_names']) == 4 and len(seq_contract['block_ids']) == 16,
            'Step27 disease or block mapping not 4x16')
    require(seq_contract['sequence_days'] == 14 and seq_contract.get('no_cross_split_windows') is True,
            'Step27 must use isolated 14-day within-split windows')
    require(all((tuned_run / choice['checkpoint']).is_file() for choice in choices48.values()),
            'At least one Step48 fitted checkpoint is missing')
    selection_file = root / 'models/spread/multidisease_step31/validation_selected_families.json'
    selection = read_json(selection_file)
    require(selection.get('mode') == 'full' and selection.get('schema_version') == 'step31-v1' and
            selection.get('test_dataset_accessed') is False,
            'Requires frozen Step31 full validation-only model selection')
    selections = selection['selected_families']
    fam = {r['target']: r['selected_family'] for r in selections}
    require(len(selections) == 21 and set(fam) == set(TARGETS) and set(fam.values()) <= FAMILIES,
            'Step31 must cover exactly all 21 heads')
    runs = {key: within(root, selection['family_runs'][key]) for key in FAMILIES}
    require(all((path / 'manifest.json').is_file() for path in runs.values()),
            'Missing frozen Step28/29/30 model family manifest')
    step28 = read_json(runs['ml_winners'] / 'manifest.json')
    require(step28['feature_columns'] == features and step28['mode'] == 'full' and
            step28['model_count'] == 21 and set(step28['targets']) == set(TARGETS),
            'Frozen Step28 manifest mismatch')
    checked_files = [selection_file, tuned_run / 'experimental_registry.json',
                     *(p / 'manifest.json' for p in runs.values())]
    hashes_before = {str(p.relative_to(root)): sha(p) for p in checked_files}
    return dict(root=root, tuned_run=tuned_run, info=tuned_info, tuned_choices=choices48,
                seq_contract=seq_contract, features=features, family=fam, runs=runs,
                selection_file=selection_file, hashes_before=hashes_before,
                checked_files=checked_files)


def load_aligned_test(root, settings):
    """Match Step31 14-day sequence-eligible origins/blocks with Step26 raw feature rows."""
    proc = root / 'data/processed'
    npz_path = proc / 'multidisease_sequence_graph_test.npz'
    require(npz_path.is_file(), f'Missing Step27 TEST sequences: {npz_path}')
    with np.load(npz_path, allow_pickle=False) as src:
        arrays = {key: src[key] for key in ('X_days', 'Y_days', 'dates', 'sample_indices')}
    ids = arrays['sample_indices'].astype(np.int64)
    origin_dates = arrays['dates'].astype(str)
    diseases = settings['seq_contract']['disease_names']
    blocks = settings['seq_contract']['block_ids']
    require(arrays['X_days'].shape == (len(origin_dates), 4, 16, 48) and
            arrays['Y_days'].shape == (len(origin_dates), 4, 16, 7, 3),
            'Unexpected Step27 TEST tensor dimensions')
    require(ids.ndim == 2 and ids.shape[1] == 2 and len(ids) > 0,
            'Empty/malformed TEST sample indices')
    require(np.all(ids[:, 0] >= 13) and np.all(ids[:, 0] < len(origin_dates)) and
            np.all((ids[:, 1] >= 0) & (ids[:, 1] < 4)),
            'Out-of-range 14-day sequence indices')
    expected_ids = np.array([(d, k) for d in range(13, len(origin_dates)) for k in range(4)],
                            dtype=np.int64)
    require(np.array_equal(ids, expected_ids),
            'TEST sequences must include exactly each eligible origin and disease once')
    origin_index = pd.to_datetime(origin_dates, errors='raise')
    require(np.all(np.diff(origin_index.values) == np.timedelta64(1,'D')),
            'Nonconsecutive TEST dates')
    require(origin_index.min().year >= 2026, 'Expected 2026 onward held-out test window')
    truth = arrays['Y_days'][ids[:, 0], ids[:, 1]]
    require(truth.shape == (len(ids),16,7,3) and np.isfinite(truth).all(),
            'Nonfinite/misaligned test labels')
    origin = [origin_dates[d] for d, _ in ids]
    dis = [diseases[k] for _, k in ids]
    keys = [(date,disease,block) for date,disease in zip(origin,dis) for block in blocks]
    df = pd.read_csv(proc / 'multidisease_features_test.csv',
                     usecols=['Forecast_Origin_Date','Disease_Name','Block_ID','Split'] +
                             settings['features'] + TARGETS,low_memory=False)
    require(df.Split.eq('test').all(), 'TEST row Split markers not test')
    require(not df.duplicated(['Forecast_Origin_Date','Disease_Name','Block_ID']).any(),
            'Duplicate TEST origin/disease/block key')
    require(set(df.Disease_Name) == set(diseases) and set(df.Block_ID) == set(blocks),
            'TEST disease/block mismatched')
    df = df.set_index(['Forecast_Origin_Date','Disease_Name','Block_ID'])
    selected = df.reindex(pd.MultiIndex.from_tuples(keys,names=df.index.names))
    require(selected[settings['features'] + TARGETS].notna().all().all(),
            'Missing aligned TEST feature/label rows')
    features = selected[settings['features']].to_numpy(dtype=np.float32)
    targets = selected[TARGETS].to_numpy(dtype=np.float32).reshape(-1,16,7,3)
    require(np.isfinite(features).all() and np.allclose(targets,truth,atol=1e-4),
            'TEST truth differs between CSV and Step27 NPZ!')
    return dict(arrays=arrays, indices=ids, origin=origin, diseases=dis,
                block_ids=blocks, labels=truth, x_tabular=features,
                features=settings['features'], disease_names=diseases,
                seq_contract=settings['seq_contract'])


def tuned_predict(settings,dataset):
    n = len(dataset['indices'])*16
    x = dataset['x_tabular']
    out = np.empty((n,7,3),dtype=np.float32)
    for day in range(1,8):
        for j,kind in enumerate(KINDS):
            target = f'Target_{kind}_Day_{day}'
            choice = settings['tuned_choices'][target]
            fitted = joblib.load(settings['tuned_run'] / choice['checkpoint'])
            inp=x
            if fitted.__class__.__module__.startswith('lightgbm'):
                raw = getattr(fitted,'feature_names_in_',None)
                if raw is not None and len(raw)==48:
                    inp=pd.DataFrame(x,columns=[str(v) for v in raw])
            raw=np.asarray(fitted.predict(inp),dtype=np.float32)
            require(raw.shape == (n,) and np.isfinite(raw).all(),
                    f'Invalid Step48 tuned model output {target}')
            if j == 1:
                raw=np.clip(raw,0,100)
            else:
                require(np.isin(raw,[0,1]).all(), f'Nonbinary predicted {target}')
            out[:,day-1,j]=raw
        print(f'  Tuned ML models: Day {day}/7 evaluated',flush=True)
    return out.reshape(len(dataset['indices']),16,7,3)


def hybrid(predictions, frozen):
    result = np.empty_like(predictions['ml_winners'])
    for day in range(1,8):
        for j,kind in enumerate(KINDS):
            target=f'Target_{kind}_Day_{day}'
            family=frozen[target]
            require(family in predictions, f'Missing forecast family {family}')
            result[:,:,day-1,j]=predictions[family][:,:,day-1,j]
    return result


def score_predictions(dataset, variants):
    truth=dataset['labels']
    disease_groups=np.asarray(dataset['diseases'])
    per_disease=[]
    for variant,pred in variants.items():
        require(pred.shape==truth.shape and np.isfinite(pred).all(),
                f'{variant}: prediction shape or finiteness mismatch')
        for day in range(1,8):
            for j,kind in enumerate(KINDS):
                target=f'Target_{kind}_Day_{day}'
                for disease in dataset['disease_names']:
                    mask=disease_groups==disease
                    require(mask.any(),f'Missing {disease} in test rows')
                    actual=truth[mask,:,day-1,j].reshape(-1)
                    p=pred[mask,:,day-1,j].reshape(-1)
                    row=dict(variant=variant,target=target,day=day,kind=kind,
                             disease=disease,records=len(actual))
                    if j==1:
                        row.update(mae=float(mean_absolute_error(actual,p)),
                                   rmse=float(np.sqrt(mean_squared_error(actual,p))),
                                   mean_error=float(np.mean(p-actual)))
                    else:
                        actual=actual.astype(int)
                        p=(p>=0.5).astype(int)
                        tn,fp,fn,tp=confusion_matrix(actual,p,labels=[0,1]).ravel()
                        row.update(macro_f1=float(f1_score(actual,p,labels=[0,1],average='macro',zero_division=0)),
                                   positive_f1=float(f1_score(actual,p,pos_label=1,zero_division=0)),
                                   positive_recall=float(recall_score(actual,p,pos_label=1,zero_division=0)),
                                   positive_precision=float(precision_score(actual,p,pos_label=1,zero_division=0)),
                                   accuracy=float(accuracy_score(actual,p)),
                                   positive_prevalence=float(np.mean(actual)),
                                   true_positive=int(tp),false_positive=int(fp),
                                   true_negative=int(tn),false_negative=int(fn))
                    per_disease.append(row)
    detail=pd.DataFrame(per_disease)
    require(len(detail)==len(variants)*21*4, 'Expected 4 disease metrics per head per variant')
    primary=[]
    for target in TARGETS:
        incidence='Incidence_Pct' in target
        metric='mae' if incidence else 'macro_f1'
        part=detail.loc[detail.target==target]
        items={var:float(part.loc[part.variant==var,metric].mean()) for var in variants}
        original=items['step31_original_hybrid']
        candidate=items['step48_candidate_hybrid']
        delta=candidate-original
        primary.append(dict(target=target,metric=metric,better='lower' if incidence else 'higher',
                            original_step31=original,step48_candidate_hybrid=candidate,
                            step48_all_tuned_ml=items['step48_all_tuned_ml'],
                            candidate_minus_original=delta,
                            candidate_improved=bool(delta < -1e-10 if incidence else delta > 1e-10),
                            equal=bool(abs(delta)<=1e-10),
                            diseases=4, test_rows=int(part.loc[part.variant=='step31_original_hybrid','records'].sum())))
    return detail,pd.DataFrame(primary)


def run(root,tuned_run,threads,batch_size):
    require(1<=threads<=16 and 1<=batch_size<=256, 'threads 1-16; batch-size 1-256')
    settings=preflight(root,tuned_run)
    r=settings['root']
    print('='*84,flush=True)
    print('STEP 48B — FROZEN STEP31 vs STEP48 HYBRID | 2026 SYNTHETIC HELD-OUT TEST',flush=True)
    print('='*84,flush=True)
    print('Test used previously in Step28; no new test tuning/selection/deployment allowed.',flush=True)
    print('Original trained models, Step31 choice registry and APIs remain unchanged.',flush=True)
    step31=load_step31(r)
    dataset=load_aligned_test(r,settings)
    print(f'Aligned test records={len(dataset["x_tabular"]):,} origins={len(set(dataset["origin"]))} '
          f'diseases=4 blocks=16',flush=True)
    predictions={}
    print('  Loading original Step28 ML winner models...',flush=True)
    predictions['ml_winners'],_ = step31.predict_ml(r,dataset,settings['runs']['ml_winners'])
    used=set(settings['family'].values())
    if 'lstm' in used:
        print('  Running frozen LSTM on identical test rows...',flush=True)
        predictions['lstm'] = step31.predict_lstm(dataset,settings['runs']['lstm'],batch_size,threads)
    if 'gcn_lstm' in used:
        print('  Running frozen GCN-LSTM on identical test rows...',flush=True)
        predictions['gcn_lstm'] = step31.predict_gcn(r,dataset,settings['runs']['gcn_lstm'],batch_size,threads)
    original=hybrid(predictions,settings['family'])
    print('  Running all 21 frozen tuned ML checkpoints...',flush=True)
    tuned=tuned_predict(settings,dataset)
    candidate_predictions={**predictions,'ml_winners':tuned}
    candidate=hybrid(candidate_predictions,settings['family'])
    variants=dict(step31_original_hybrid=original,
                  step48_candidate_hybrid=candidate,
                  step48_all_tuned_ml=tuned)
    detail,summary=score_predictions(dataset,variants)
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    report=r/'outputs/reports/multidisease_step48b'/f'full_{stamp}'
    report.mkdir(parents=True,exist_ok=False)
    detail.to_csv(report/'heldout_test_per_disease.csv',index=False)
    summary.to_csv(report/'heldout_test_hybrid_comparison.csv',index=False)
    hashes_after={str(path.relative_to(r)):sha(path) for path in settings['checked_files']}
    require(hashes_after==settings['hashes_before'], 'Protected selection/model manifests changed')
    audit=dict(schema_version='step48b-v1',status='PASS_HELDOUT_COMPARISON_SYNTHETIC',
               study_setting='SIMULATED_BLOCKS_NOT_REAL_ESTATE',test_split='2026 historical synthetic',
               note='Test already accessed in Step28; independent of Step48 fitting but NOT pristine research holdout.',
               test_used_to_select_models=False,models_retrained=False,models_promoted=False,
               aligned_test_origin_days=len(set(dataset['origin'])),
               aligned_test_records=len(dataset['x_tabular']),
               alignment='identical 14-day-history eligible origins, 4 diseases, 16 blocks, 48 unscaled Step26 features; Step27 labels cross-checked',
               test_first_origin=min(dataset['origin']),test_last_origin=max(dataset['origin']),
               original_family_choices=settings['family'],
               tuned_model_run=str(settings['tuned_run'].relative_to(r)),
               fixed_step31_family_registry=str(settings['selection_file'].relative_to(r)),
               candidate_hybrid_definition='Replace ONLY ml_winners heads in frozen Step31 21-head family routing with Step48 tuned ML; keep frozen LSTM/GCN heads',
               all_tuned_ml_definition='Use Step48 tuned tabular estimator for every one of the 21 output heads',
               per_target_improved=int(summary.candidate_improved.sum()),
               per_target_worse=int((~summary.candidate_improved & ~summary.equal).sum()),
               per_target_equal=int(summary.equal.sum()),
               report_files=['heldout_test_per_disease.csv','heldout_test_hybrid_comparison.csv'],
               protected_files_unchanged=True,protected_manifest_sha256=hashes_after,
               limitations=['2026 TEST was previously accessed in Step28, not a newly unseen external test set',
                            'Simulation only; not measured on a real Nuwara Eliya tea estate',
                            'Equal-disease macro F1 can mask low positive recall in new-onset task',
                            'No test-based model selection, retuning or deployment should follow',
                            'Performance differences have no uncertainty intervals and are exploratory'])
    (report/'step48b_heldout_audit.json').write_text(json.dumps(audit,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print('='*84,flush=True)
    print(f'STEP48B — PASS | 21/21 heads | improved={audit["per_target_improved"]} '
          f'worse={audit["per_target_worse"]} equal={audit["per_target_equal"]}',flush=True)
    print(f'Report: {report}',flush=True)
    print('No model promotion. NEVER retune/reselect based on these test results.',flush=True)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--component-root',type=Path,default=Path(__file__).resolve().parents[2])
    p.add_argument('--tuned-run-dir',type=Path,required=True,
                   help='Exact Step48 ALL run directory saved under models/spread/multidisease_step48')
    p.add_argument('--threads',type=int,default=2)
    p.add_argument('--batch-size',type=int,default=8)
    p.add_argument('--preflight-only',action='store_true',help='Validate artifacts but do NOT open TEST')
    a=p.parse_args()
    settings=preflight(a.component_root,a.tuned_run_dir)
    if a.preflight_only:
        print('STEP48B PREFLIGHT PASS: tuned and frozen hybrid artifacts consistent; TEST NOT OPENED.')
        return
    run(a.component_root,a.tuned_run_dir,a.threads,a.batch_size)

if __name__=='__main__':
    main()
