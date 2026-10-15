"""Step 32: export a historical VALIDATION demo snapshot for four simulated diseases.

This is NOT a live/current forecast and does NOT calculate evaluation metrics.
It routes each of the 21 targets through the Step 31 validation-selected
family and records uncalibrated scores with explicit simulation provenance.
For later dynamic FastAPI prediction, import SelectedSpreadPredictor and supply
valid preprocessed new-origin data; the demo exporter does not implement that.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from selected_spread_inference import SelectedSpreadPredictor, require

ROOT = Path(__file__).resolve().parents[2]


def dump_json(path:Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def run(root:Path, mode:str, origin_date:str | None, threads:int):
    root=root.resolve()
    require(mode in {'smoke','full'}, 'mode must be smoke or full')
    router = SelectedSpreadPredictor(root, threads=threads)
    processed = root / 'data/processed'
    seq_path = processed / 'multidisease_sequence_graph_validation.npz'
    require(seq_path.is_file(), 'Missing Step27 VALIDATION sequences')
    with np.load(seq_path, allow_pickle=False) as npz:
        x_days = npz['X_days']
        dates = npz['dates'].astype(str)
        indices = npz['sample_indices'].astype(np.int32)
    require(x_days.shape[1:] == (4,16,48), 'Expected 4 diseases, 16 blocks, 48 features')
    valid_end = sorted(set(int(x) for x in indices[:,0]))
    require(valid_end and min(valid_end) >= 13, 'No complete 14-day VALIDATION histories')
    end = valid_end[-1]
    if origin_date is not None:
        end_options = [i for i in valid_end if dates[i] == origin_date]
        require(len(end_options) == 1, 'Requested date missing a complete VALIDATION 14-day window')
        end=end_options[0]
    origin = str(dates[end])
    expected_indices = {(end,i) for i in range(4)}
    require(expected_indices.issubset(set(map(tuple, indices.tolist()))),
            'Not all four diseases eligible at the selected date')

    feature_cols = router.features
    meta_cols=['Forecast_Origin_Date','Disease_Name','Block_ID','Split']
    frame = pd.read_csv(processed / 'multidisease_features_validation.csv',
                        usecols=meta_cols+feature_cols, low_memory=False)
    require(frame.Split.eq('validation').all(), 'Step26 split is not validation')
    require(not frame.duplicated(['Forecast_Origin_Date','Disease_Name','Block_ID']).any(),
            'Duplicate origin/disease/block keys')
    # Same train-fitted scaling used for Step27 day tensors. This is a check,
    # not a second fit; Step28 ML still consumes UNscaled Step26 features.
    prep = joblib.load(processed / 'multidisease_step26_feature_pipeline.joblib')
    require(prep.get('training_only_fit') is True and
            prep.get('feature_columns') == feature_cols,
            'Missing/mismatched Step26 TRAIN-fitted pipeline')
    scaler=prep['full_feature_scaler_train_only']
    require(scaler.n_features_in_ == 48, 'Unexpected Step26 scaler dimension')
    n_classes=1 if mode=='smoke' else 4
    diseases = router.diseases[:n_classes]
    records=[]
    for di,disease in enumerate(diseases):
        history=x_days[end-13:end+1,di]  # ALREADY train-scaled in Step27
        require(history.shape == (14,16,48), 'Misaligned Step27 history')
        subset = frame[(frame.Forecast_Origin_Date == origin) & (frame.Disease_Name == disease)]
        require(len(subset)==16 and set(subset.Block_ID) == set(router.blocks),
                f'Missing one or more blocks at {origin} / {disease}')
        tabular=subset.set_index('Block_ID').loc[router.blocks, feature_cols].to_numpy(dtype=np.float32)
        require(np.isfinite(tabular).all(), 'Nonfinite Step26 feature values')
        expected_scaled=scaler.transform(tabular).astype(np.float32)
        require(np.allclose(history[-1],expected_scaled,rtol=1e-4,atol=1e-4),
                'Step26/27 origin feature mismatch (scaled vs unscaled)')
        predictions=router.predict_disease(disease, history_scaled=history,
                                           tabular_origin=tabular)
        for rec in predictions:
            rec['forecast_origin_date']=origin
            rec['forecast_target_date']=(datetime.fromisoformat(origin) +
                                         timedelta(days=rec['horizon_day'])).date().isoformat()
            rec['record_type']='HISTORICAL_VALIDATION_DEMONSTRATION_NOT_LIVE'
            rec['live_estate_forecast']=False
        records.extend(predictions)
        print(f'  {disease}: {len(predictions)} block/day predictions', flush=True)

    require(len(records) == len(diseases)*16*7, 'Unexpected number of predictions')
    export_dir = root / 'outputs/dashboard/spread'
    export_dir.mkdir(parents=True, exist_ok=True)
    prefix = 'step32_smoke' if mode=='smoke' else 'step32_validation_snapshot'
    csv_path=export_dir / f'{prefix}.csv'
    json_path=export_dir / f'{prefix}.json'
    manifest_path=export_dir / f'{prefix}_metadata.json'
    pd.DataFrame(records).to_csv(csv_path,index=False)
    dump_json(json_path, {'snapshot_type':'historical_validation_demonstration',
                          'forecast_origin_date':origin,'records':records})
    model_counts=dict(Counter(router.family_choice.values()))
    meta={
        'schema_version':'step32-v1',
        'mode':mode, 'status':'PASS_DEMO_EXPORT_NOT_LIVE',
        'forecast_origin_date':origin, 'date_context':'Historical validation data, not current time',
        'disease_names':diseases, 'block_ids':router.blocks,
        'horizon_days':list(range(1,8)),
        'total_records':len(records), 'model_family_target_counts':model_counts,
        'selection_file':'models/spread/multidisease_step31/validation_selected_families.json',
        'simulation_provenance':'SIMULATION_ONLY_NOT_FIELD_VALIDATED',
        'trained_models_field_validated':False,
        'test_data_accessed':False, 'test_metrics_computed':False,
        'data_inputs':{'ml':'Step26 already-engineered 48 unscaled features',
                       'lstm_gcn':'Step27 14-day TRAIN-scaled windows'},
        'classification': 'Binary predicted class; scores when available are uncalibrated',
        'incidence_units':'Percentage of inspected bushes (synthetic estimate; not validated)',
        'limits':[
            'Historical validation snapshot, not a forecast for the current estate/date',
            'Cannot reforecast from new observations without rebuilding Step25/26 features, Step27 scaled history and applying identical contracts',
            'Model families selected on reused validation data; optimistic selection possible',
            'Synthetic estate blocks, four simulated diseases, source climate location not field verified',
            'No expert-verified risk thresholds, no treatment decisions, no calibrated probabilities',
        ],
        'csv':str(csv_path.relative_to(root)),
        'json':str(json_path.relative_to(root)),
    }
    dump_json(manifest_path,meta)
    # Registry for eventual FastAPI integration. The full selection manifest is
    # not modified; registry points to already-saved models by relative paths.
    registry=root / 'models/spread/multidisease_step32/selected_model_registry.json'
    if mode=='full':
        dump_json(registry,{
            'schema_version':'step32-registry-v1',
            'scope':'SIMULATION_ONLY_NOT_FIELD_VALIDATED',
            'selection':meta['selection_file'],
            'model_runs':router.selection['family_runs'],
            'model_family_target_counts':model_counts,
            'disease_names':router.diseases,'block_ids':router.blocks,
            'features':feature_cols,'lookback_days':14,'horizon_days':7,
            'require_preprocessed_history':True,
            'live_observation_feature_pipeline_included':False,
            'dashboard_demo':str(csv_path.relative_to(root)),
            'warning':'Historical validation demo only; uncalibrated and not field-validated',
        })
    print('='*76,flush=True)
    print(f'STEP 32 - SELECTED MODEL ROUTING + DASHBOARD DEMO | {mode.upper()}',flush=True)
    print('='*76,flush=True)
    print(f'Historical VALIDATION origin: {origin}, diseases={len(diseases)}, blocks=16, days=7',flush=True)
    print(f'Rows exported: {len(records)} | Family selections: {model_counts}',flush=True)
    print('CSV:',csv_path,flush=True)
    print('JSON:',json_path,flush=True)
    print('Metadata:',manifest_path,flush=True)
    if mode=='full':
        print('Model registry:',registry,flush=True)
    print('PASS: saved-model routing and historical dashboard-demo export.',flush=True)
    print('WARNING: NOT a current-date, real-estate, or field-validated prediction.',flush=True)
    print('NO test set loaded; NO training or model selection performed.',flush=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,default=ROOT)
    ap.add_argument('--mode',choices=['smoke','full'],default='smoke')
    ap.add_argument('--origin-date',default=None,
                    help='Optional historical validation date YYYY-MM-DD; default: latest eligible')
    ap.add_argument('--threads',type=int,default=2)
    args=ap.parse_args()
    run(args.root,args.mode,args.origin_date,args.threads)

if __name__=='__main__':
    main()
