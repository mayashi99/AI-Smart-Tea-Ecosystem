"""Step42 dynamic officer-conditioned SIMULATION at a saved historical validation origin.

NOT a real-time/current-date estate forecast. Builds exact Step25/26 features from
origin-day changes and preceding synthetic observations; executes saved Step31
selected models (ML/LSTM). Never reads Target_* columns or test files.

Single-process, file-based demonstration. Full multi-user concurrency is unsupported.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import json
import math
import os
import tempfile
import threading
import uuid

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BLOCKS = [f'B{x:02d}' for x in range(1,17)]
DISEASES = ['Brown Blight','Grey Leaf','Red Rust','Red Spider Mite']
BASE_RAW = [
    'Observation_Available','Inspected_Bushes','Symptomatic_Bushes',
    'Sample_Incidence_Pct','Latest_Observed_Incidence_Pct',
    'Days_Since_Last_Inspection','T2M','RH2M','PRECTOTCORR',
    'ALLSKY_SFC_SW_DWN','Humidity_Mean_7D','Rainfall_Sum_7D',
    'Neighbor_Latest_Incidence_Mean_Pct','Neighbor_Recent_Positive_Count',
]
SOURCE_COLS = ['Date','Estate_ID','Block_ID','Disease_Name'] + BASE_RAW
LAG_SOURCES = [
    'Latest_Observed_Incidence_Pct', 'Neighbor_Latest_Incidence_Mean_Pct',
    'T2M', 'RH2M', 'PRECTOTCORR',
]
ROLL_SOURCES = [
    ('Latest_Observed_Incidence_Pct','mean'),
    ('Neighbor_Latest_Incidence_Mean_Pct','mean'),
    ('RH2M','mean'),
    ('PRECTOTCORR','sum'),
    ('Observation_Available','sum'),
]
STATS = ['Grid_Row','Grid_Column','Relative_Vulnerability']
CSV_FIELDS = [
    'observation_id','forecast_origin_date','block_id','disease_name',
    'inspected_bushes','symptomatic_bushes','incidence_percent','created_at_utc',
]
_LOCK = threading.RLock()


def demand(test, msg):
    if not test: raise ValueError(msg)


def read_json(path):
    demand(path.is_file(), f'Missing prerequisite file: {path}')
    return json.loads(path.read_text(encoding='utf-8'))


def origin_from_snapshot(root=ROOT):
    info = read_json(Path(root) / 'outputs/dashboard/spread/step32_validation_snapshot_metadata.json')
    demand(info.get('mode') == 'full' and info.get('status') == 'PASS_DEMO_EXPORT_NOT_LIVE',
           'Step32 FULL historical snapshot required')
    origin = date.fromisoformat(info['forecast_origin_date'])
    demand(date(2025,1,8) <= origin <= date(2025,12,24),
           'Only the validated 2025 historical-origin simulation is allowed')
    return origin


def validate_observation(block_id, disease_name, inspected_bushes, symptomatic_bushes):
    demand(isinstance(block_id,str) and block_id in BLOCKS, 'Select B01..B16')
    demand(isinstance(disease_name,str) and disease_name in DISEASES, 'Unsupported disease')
    demand(type(inspected_bushes) is int and 1 <= inspected_bushes <= 1000000,
           'Inspected bushes: integer 1..1000000')
    demand(type(symptomatic_bushes) is int and 0 <= symptomatic_bushes <= inspected_bushes,
           'Symptomatic bushes: integer 0..inspected bushes')
    return {'block_id':block_id,'disease_name':disease_name,
            'inspected_bushes':inspected_bushes,'symptomatic_bushes':symptomatic_bushes,
            'incidence_percent':round(100*symptomatic_bushes/inspected_bushes,6)}


def runtime_file(root=ROOT):
    return Path(root) / 'data/runtime/officer_observations.csv'


def previous_updates(root, origin):
    f = runtime_file(root)
    if not f.exists(): return []
    df = pd.read_csv(f, encoding='utf-8-sig', keep_default_na=False)
    demand(list(df.columns)==CSV_FIELDS, 'Unexpected runtime CSV schema')
    found=[]
    for record in df.to_dict(orient='records'):
        if record['forecast_origin_date'] != origin.isoformat(): continue
        found.append(validate_observation(
            record['block_id'],record['disease_name'],
            int(record['inspected_bushes']),int(record['symptomatic_bushes'])))
    return found


def prepare_24h_inputs(root, origin, updates, baseline_check=False):
    """Build all four diseases' origin-observable 48-column data for 14 days.

    The 21-day source is exactly 14 model-history days plus 7 preceding lag days.
    Only a historical VALIDATION period is read; no Target_* columns or held-out test.
    """
    root=Path(root).resolve()
    earliest=origin-timedelta(days=20)
    source=root/'data/synthetic/synthetic_block_records_multidisease.csv'
    demand(source.is_file(), f'Missing Step23 source: {source}')
    raw=pd.read_csv(source,usecols=SOURCE_COLS,low_memory=False,encoding='utf-8-sig')
    raw['Date']=pd.to_datetime(raw.Date, errors='raise')
    raw=raw.loc[(raw.Date>=pd.Timestamp(earliest)) & (raw.Date<=pd.Timestamp(origin))].copy()
    demand(len(raw)==21*4*16, f'Missing contiguous 21-day provenance; rows={len(raw)}')
    demand(not raw.duplicated(['Date','Disease_Name','Block_ID']).any(), 'Duplicate date/disease/block records')
    demand(set(raw.Disease_Name)==set(DISEASES) and set(raw.Block_ID)==set(BLOCKS), 'Unexpected disease/blocks')
    days=sorted(raw.Date.unique())
    demand(len(days)==21 and all((pd.Timestamp(days[i])-pd.Timestamp(days[i-1])).days==1
          for i in range(1,21)), 'Source history not contiguous')
    demand(raw.Estate_ID.nunique()==1, 'Simulation should contain exactly one estate')
    demand(not any(c.startswith('Target_') for c in raw.columns), 'Future target data in runtime')

    # Replace current-origin inspections; last submitted observation wins.
    applied={}
    for item in updates:
        v=validate_observation(item['block_id'],item['disease_name'],
                               item['inspected_bushes'],item['symptomatic_bushes'])
        applied[(v['block_id'],v['disease_name'])]=v
    today=raw.Date.eq(pd.Timestamp(origin))
    for (block,disease), v in applied.items():
        take=today & raw.Block_ID.eq(block) & raw.Disease_Name.eq(disease)
        demand(int(take.sum())==1, f'Missing origin row: {block} {disease}')
        ix=raw.index[take][0]
        raw.loc[ix,'Observation_Available']=1
        raw.loc[ix,'Inspected_Bushes']=v['inspected_bushes']
        raw.loc[ix,'Symptomatic_Bushes']=v['symptomatic_bushes']
        raw.loc[ix,'Sample_Incidence_Pct']=v['incidence_percent']
        raw.loc[ix,'Latest_Observed_Incidence_Pct']=v['incidence_percent']
        raw.loc[ix,'Days_Since_Last_Inspection']=0

    # Neighbor values on origin day react to EVERY submitted block observation.
    edges=pd.read_csv(root/'data/synthetic/block_adjacency.csv',encoding='utf-8-sig')
    demand({'Source_Block','Target_Block'}.issubset(edges.columns), 'Bad adjacency graph')
    graph={b:[] for b in BLOCKS}
    for row in edges.itertuples(index=False):
        demand(row.Source_Block in graph and row.Target_Block in graph, 'Unknown graph node')
        graph[row.Target_Block].append(row.Source_Block)
    demand(all(graph.values()), 'Some blocks have no neighbors')
    affected_diseases={disease for _,disease in applied}
    for disease in DISEASES:
        if disease not in affected_diseases: continue
        subset=raw.loc[today & raw.Disease_Name.eq(disease)]
        lookup=subset.set_index('Block_ID')['Latest_Observed_Incidence_Pct'].to_dict()
        demand(set(lookup)==set(BLOCKS), 'Incomplete origin adjacency values')
        for block in BLOCKS:
            ix=raw.index[today & raw.Disease_Name.eq(disease) & raw.Block_ID.eq(block)][0]
            raw.loc[ix,'Neighbor_Latest_Incidence_Mean_Pct']=float(np.mean([lookup[b] for b in graph[block]]))
    # On the same origin day Neighbor_Recent_Positive_Count uses PREVIOUS 7 days;
    # hence it is unchanged when updating observations on the current day.

    blocks=pd.read_csv(root/'data/synthetic/estate_blocks.csv',encoding='utf-8-sig')
    demand(not blocks.Block_ID.duplicated().any(), 'Block metadata duplicated')
    estate=str(raw.Estate_ID.iloc[0]); demand((blocks.Estate_ID.astype(str)==estate).all(),'Estate mismatch')
    raw=raw.merge(blocks[['Block_ID']+STATS],on='Block_ID',how='left',validate='many_to_one')
    demand(raw[STATS].notna().all().all(), 'Static block metadata missing')
    raw['Forecast_Origin_Date']=raw.Date.dt.strftime('%Y-%m-%d')
    dt=raw.Date
    raw['Day_Of_Year_Sin']=np.sin(2*np.pi*dt.dt.dayofyear/365.25)
    raw['Day_Of_Year_Cos']=np.cos(2*np.pi*dt.dt.dayofyear/365.25)
    raw['Weekday_Sin']=np.sin(2*np.pi*dt.dt.dayofweek/7)
    raw['Weekday_Cos']=np.cos(2*np.pi*dt.dt.dayofweek/7)

    processed=root/'data/processed'
    prep25=joblib.load(processed/'multidisease_train_fitted_preprocessor.joblib')
    prep26=joblib.load(processed/'multidisease_step26_feature_pipeline.joblib')
    contract=read_json(processed/'multidisease_feature_contract.json')
    seq=read_json(processed/'multidisease_sequence_graph_contract.json')
    features=contract['feature_columns']
    demand(prep25.get('training_only_fit') is True and prep26.get('training_only_fit') is True,
           'Preprocessing not train fitted')
    demand(len(features)==48 and len(prep25['feature_columns'])==28, 'Unexpected feature count')
    demand(prep26['feature_columns']==features==seq['input_feature_columns'], 'Schema mismatch')
    demand(seq['sequence_days']==14 and seq['block_ids']==BLOCKS and seq['disease_names']==DISEASES,
           'Sequence order/scope mismatch')
    demand(prep25['disease_names']==DISEASES, 'Step25 disease order mismatch')

    nums=raw[prep25['numeric_features']].apply(pd.to_numeric,errors='raise')
    nparr=prep25['imputer'].transform(nums)
    base=pd.DataFrame(nparr,columns=prep25['numeric_features'],index=raw.index)
    for name,flag in zip(['Inspected_Bushes','Symptomatic_Bushes','Sample_Incidence_Pct'],prep25['missing_flags']):
        base[flag]=nums[name].isna().astype(int)
    for name,oh in zip(DISEASES,prep25['disease_onehot']):
        base[oh]=raw.Disease_Name.eq(name).astype(int)
    demand(list(base.columns)==prep25['feature_columns'], 'Step25 feature column order changed')

    ordered=raw.sort_values(['Estate_ID','Disease_Name','Block_ID','Date'])
    grouped=ordered.groupby(['Estate_ID','Block_ID','Disease_Name'],sort=False,observed=True)
    histories=pd.DataFrame(index=ordered.index)
    for name in LAG_SOURCES:
        for gap in (1,3,7):
            col=f'Past_{name}_Lag{gap}D'
            histories[col]=grouped[name].shift(gap)
    for name, operation in ROLL_SOURCES:
        col=f'Past_{name}_Rolling7D_{operation}'
        histories[col]=grouped[name].transform(
            lambda s: getattr(s.shift(1).rolling(7,min_periods=1),operation)())
    lagcols=prep26['historical_columns']
    demand(list(histories.columns)==lagcols and len(lagcols)==20, 'Step26 lag/rolling features changed')
    histories=histories.reindex(raw.index)
    lagarr=prep26['lag_imputer'].transform(histories[lagcols])
    lagged=pd.DataFrame(lagarr,columns=lagcols,index=raw.index)
    matrix=pd.concat([raw[['Forecast_Origin_Date','Date','Disease_Name','Block_ID']],base,lagged],axis=1)
    demand(list(matrix.columns[4:])==features,'Feature order incorrect')
    window=matrix.loc[matrix.Date>=pd.Timestamp(origin-timedelta(days=13))].copy()
    demand(len(window)==14*4*16, 'Incomplete 14-day sequence')
    demand(np.isfinite(window[features].to_numpy(dtype=float)).all(), 'Nonfinite model features')

    # Optional exact reconstruction proof before any officer update is applied.
    if baseline_check:
        demand(not applied, 'Baseline equivalence check requires no officer changes')
        original=pd.read_csv(processed/'multidisease_features_validation.csv',
                             usecols=['Forecast_Origin_Date','Block_ID','Disease_Name']+features,low_memory=False)
        target_dates=set(window.Forecast_Origin_Date)
        original=original.loc[original.Forecast_Origin_Date.isin(target_dates)].copy()
        key=['Forecast_Origin_Date','Disease_Name','Block_ID']
        joined=window.merge(original,on=key,how='left',validate='one_to_one',suffixes=('_rebuilt','_saved'),indicator=True)
        demand(len(joined)==len(window) and joined._merge.eq('both').all(), 'Baseline feature keys mismatch')
        rebuilt=joined[[f'{x}_rebuilt' for x in features]].to_numpy(dtype=float)
        saved=joined[[f'{x}_saved' for x in features]].to_numpy(dtype=float)
        max_delta=float(np.max(np.abs(rebuilt-saved)))
        demand(np.allclose(rebuilt,saved,atol=1e-3,rtol=1e-4),
               f'Baseline model inputs do not match Step26: max_diff={max_delta}')
    else:
        max_delta=None
    return {'window':window, 'scaler':prep26['full_feature_scaler_train_only'],
            'feature_columns':features,'origin':origin,'applied':list(applied.values()),
            'baseline_max_abs_delta':max_delta}


def arrays_for_disease(built,disease):
    demand(disease in DISEASES, 'Unsupported disease')
    frame=built['window']; features=built['feature_columns']; origin=built['origin']
    subset=frame.loc[frame.Disease_Name.eq(disease)].sort_values(['Date','Block_ID']).copy()
    dates=sorted(subset.Date.unique())
    demand(len(dates)==14 and all(len(subset.loc[subset.Date.eq(d)])==16 for d in dates),
           'Incomplete 14x16 block history')
    raw=subset[features].to_numpy(dtype=np.float32).reshape(14,16,48)
    scaled=built['scaler'].transform(raw.reshape(-1,48)).astype(np.float32).reshape(14,16,48)
    tabular=raw[-1]
    demand(np.isfinite(scaled).all() and np.isfinite(tabular).all(),'Nonfinite model matrix')
    return scaled,tabular


def demo_alert(row):
    inc=float(row['incidence_percent_prediction'])
    act=int(row['activity_predicted_class']); onset=int(row['new_onset_predicted_class'])
    return 'DEMO_HIGH' if inc>=15 or (act and onset) else 'DEMO_WATCH' if inc>=5 or act or onset else 'DEMO_INFO'


def dynamic_predict(root, block_id, disease_name, inspected_bushes, symptomatic_bushes,
                    *, save=False, predictor=None, check_saved_baseline=False):
    """Run real selected models on observation-overlaid input, then optionally persist.

    All service calls use the same saved historical origin; no fake current-day claim.
    Calls are serialized within this Python process (use one uvicorn worker).
    """
    root=Path(root).resolve()
    obs=validate_observation(block_id,disease_name,inspected_bushes,symptomatic_bushes)
    origin=origin_from_snapshot(root)
    with _LOCK:
        earlier=previous_updates(root,origin)
        old_base=prepare_24h_inputs(root,origin,earlier,baseline_check=check_saved_baseline and not earlier) if check_saved_baseline and not earlier else None
        built=prepare_24h_inputs(root,origin,earlier+[obs])
        scaled,tabular=arrays_for_disease(built,disease_name)
        if predictor is None:
            # Import only at prediction time; project checkpoint loading can take time.
            from selected_spread_inference import SelectedSpreadPredictor
            predictor=SelectedSpreadPredictor(root,threads=2)
        predictions=predictor.predict_disease(disease_name,scaled,tabular)
        demand(len(predictions)==112,'Expected 16 blocks x 7 days from trained router')
        chosen=[dict(p) for p in predictions if p['block_id']==block_id]
        demand(len(chosen)==7 and {int(r['horizon_day']) for r in chosen}==set(range(1,8)),
               'Missing or duplicated selected-block horizons')
        for r in chosen:
            r['forecast_origin_date']=origin.isoformat()
            r['forecast_target_date']=(origin+timedelta(days=int(r['horizon_day']))).isoformat()
            r['demo_alert_level']=demo_alert(r)
        result={
            'schema_version':'step42-dynamic-officer-simulation-v1',
            'mode':'OFFICER_CONDITIONED_HISTORICAL_VALIDATION_SIMULATION',
            'is_current_live_estate_forecast':False,
            'actual_saved_model_inference':True,
            'synthetic_estate':True,
            'climate_venue_verified':False,
            'forecast_origin_date':origin.isoformat(),
            'selected_block_id':block_id,'disease_name':disease_name,
            'submitted_observation':obs,
            'previous_officer_updates_applied':len({(r['block_id'],r['disease_name']) for r in earlier}),
            'feature_columns_count':48,'history_window_days':14,
            'selected_block_daily_forecast':chosen,
            'all_block_forecast_for_selected_disease':[
                {**dict(r),'forecast_origin_date':origin.isoformat(),
                 'forecast_target_date':(origin+timedelta(days=int(r['horizon_day']))).isoformat()}
                for r in predictions],
            'limitations':[
                'Historical 2025 validation-origin simulation, NOT an October 2026 real-time forecast',
                'Simulated blocks and inspections, single unverified climate point',
                'Predictions may remain identical after inputs change; changes to features are verified separately',
                'Uncalibrated model probabilities and unvalidated illustrative alert thresholds',
                'Train/validation feature selection is exploratory; not new independent field validation',
                'One server process only for file-based persistence',
            ],
            'saved':False,
        }
        if old_base is not None:
            result['baseline_feature_parity_max_abs_difference']=old_base['baseline_max_abs_delta']
        if save:
            # Persist only after successful inference to avoid invalid runtime records.
            _persist(root,origin,obs)
            result['saved']=True
            _write_json(root/'outputs/dashboard/dynamic/step42_latest_officer_forecast.json', result)
        return result


def _persist(root,origin,obs):
    path=runtime_file(root)
    path.parent.mkdir(parents=True,exist_ok=True)
    existing=pd.read_csv(path,encoding='utf-8-sig') if path.exists() else pd.DataFrame(columns=CSV_FIELDS)
    demand(list(existing.columns)==CSV_FIELDS,'Runtime schema changed; refusing write')
    row={**obs,'observation_id':uuid.uuid4().hex,
         'forecast_origin_date':origin.isoformat(),
         'created_at_utc':datetime.now(timezone.utc).isoformat()}
    incoming=pd.DataFrame([row],columns=CSV_FIELDS)
    updated=(incoming if existing.empty else pd.concat([existing,incoming],ignore_index=True))[CSV_FIELDS]
    fd,tmp=tempfile.mkstemp(prefix='step42_',suffix='.csv',dir=str(path.parent));os.close(fd)
    try:
        updated.to_csv(tmp,index=False)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def _write_json(path, obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='step42_',suffix='.json',dir=str(path.parent));os.close(fd)
    try:
        Path(tmp).write_text(json.dumps(obj,indent=2,allow_nan=False),encoding='utf-8')
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
