"""Step51 — strict current-date 7-day inference from recent block/climate records.

This is an additive path. It does NOT relabel Step42 2025 forecasts.
The 21-day input files must contain genuine recent records for all blocks/diseases,
including explicit rows for days with no inspection and actual climate observations.
The selected predictor was trained on a synthetic dataset and is NOT field-validated.
A current date alone does not make a prediction accurate or operationally approved.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import json
import os
import tempfile
import uuid

import numpy as np
import pandas as pd

from dynamic_spread_service import (
    ROOT, BLOCKS, DISEASES, SOURCE_COLS, CSV_FIELDS, BASE_RAW, STATS, _LOCK,
    validate_observation, demand, prepare_24h_inputs, arrays_for_disease,
)

SLT = timezone(timedelta(hours=5, minutes=30))
REQUIRED_DAYS = 21  # 14 history + 7 preceding days for rolling/lag features
CURRENT_DAILY_CSV = 'data/runtime/current_daily_block_records.csv'
CURRENT_BLOCKS_CSV = 'data/runtime/current_estate_blocks.csv'
CURRENT_EDGES_CSV = 'data/runtime/current_block_adjacency.csv'
CURRENT_OBSERVATIONS_CSV = 'data/runtime/current_officer_observations.csv'
CURRENT_LATEST_JSON = 'outputs/dashboard/dynamic/step51_latest_current_forecast.json'


class CurrentDataUnavailable(Exception):
    """Recent field/climate inputs are missing or incompatible with the trained model."""


def sri_lanka_today() -> date:
    return datetime.now(SLT).date()


def current_paths(root):
    root = Path(root).resolve()
    return (root / CURRENT_DAILY_CSV, root / CURRENT_BLOCKS_CSV, root / CURRENT_EDGES_CSV)


def _need(condition, message):
    if not condition:
        raise CurrentDataUnavailable(message)


def validate_current_data(root, origin: date):
    """Validate exact 21-day observable input contract, without fabricating any rows."""
    source_path, block_path, edges_path = current_paths(root)
    for p in (source_path, block_path, edges_path):
        _need(p.is_file(), f'Required current-date input missing: {p}')

    try:
        raw = pd.read_csv(source_path, encoding='utf-8-sig', low_memory=False)
        _need(set(SOURCE_COLS).issubset(raw.columns),
              'Current daily CSV missing columns: ' + ', '.join(sorted(set(SOURCE_COLS)-set(raw.columns))))
        _need(not any(c.startswith('Target_') for c in raw.columns),
              'Future-target data must not be included in input CSV')
        _need(len(raw) == REQUIRED_DAYS * len(BLOCKS) * len(DISEASES),
              f'Expected {REQUIRED_DAYS * len(BLOCKS) * len(DISEASES)} unique daily rows (21 days x 16 blocks x 4 diseases)')
        dates = pd.to_datetime(raw['Date'], errors='raise')
        _need(dates.dt.normalize().equals(dates), 'Date must be a calendar day (YYYY-MM-DD)')
        wanted = {origin - timedelta(days=i) for i in range(REQUIRED_DAYS)}
        _need(set(dates.dt.date) == wanted,
              f'Current daily CSV must cover all dates {origin-timedelta(days=20)} through {origin}, with no stale or future dates')
        _need(set(raw['Block_ID']) == set(BLOCKS), 'Current data must include exactly B01..B16')
        _need(set(raw['Disease_Name']) == set(DISEASES), 'Current data must contain all four forecast diseases')
        _need(not raw.duplicated(['Date', 'Disease_Name', 'Block_ID']).any(), 'Duplicate daily disease/block input rows')
        _need(raw['Estate_ID'].notna().all() and raw['Estate_ID'].nunique() == 1,
              'Expected one consistent estate identifier')

        required_climate = ['T2M', 'RH2M', 'PRECTOTCORR', 'ALLSKY_SFC_SW_DWN',
                            'Humidity_Mean_7D', 'Rainfall_Sum_7D']
        climate = raw[required_climate].apply(pd.to_numeric, errors='coerce')
        _need(np.isfinite(climate.to_numpy(dtype=float)).all(),
              'Recent climate readings and their observed rolling summaries must be supplied; do not replace missing values with invented data')
        _need(climate['RH2M'].between(0,100).all() and climate['Humidity_Mean_7D'].between(0,100).all(),
              'Relative humidity must be within 0..100%')
        _need((climate[['PRECTOTCORR','Rainfall_Sum_7D','ALLSKY_SFC_SW_DWN']] >= 0).all().all(),
              'Precipitation, rolling rainfall and solar radiation cannot be negative')

        available = pd.to_numeric(raw['Observation_Available'], errors='coerce')
        _need(available.notna().all() and available.isin([0,1]).all(),
              'Observation_Available must be 0 or 1 on every day/block/disease row')
        observed = raw.loc[available.eq(1)].copy()
        _need(not observed.empty, 'At least some real field inspections are needed within the recent input period')
        inspected = pd.to_numeric(observed['Inspected_Bushes'], errors='coerce')
        symptomatic = pd.to_numeric(observed['Symptomatic_Bushes'], errors='coerce')
        incidence = pd.to_numeric(observed['Sample_Incidence_Pct'], errors='coerce')
        _need(np.isfinite(inspected).all() and (inspected >= 1).all() and (inspected % 1 == 0).all(),
              'Observed records need positive integer Inspected_Bushes')
        _need(np.isfinite(symptomatic).all() and (symptomatic >= 0).all() and (symptomatic <= inspected).all() and (symptomatic % 1 == 0).all(),
              'Observed records need valid integer Symptomatic_Bushes')
        _need(np.isfinite(incidence).all() and np.allclose(incidence,100*symptomatic/inspected,atol=0.01),
              'Observed disease incidence must equal 100 * symptomatic / inspected')

        metadata = pd.read_csv(block_path, encoding='utf-8-sig')
        _need({'Block_ID','Estate_ID',*STATS}.issubset(metadata.columns),
              'Block metadata CSV must contain Block_ID, Estate_ID, Grid_Row, Grid_Column, Relative_Vulnerability')
        _need(len(metadata)==16 and set(metadata['Block_ID'])==set(BLOCKS) and not metadata['Block_ID'].duplicated().any(),
              'Block metadata must include 16 unique blocks')
        _need((metadata['Estate_ID'].astype(str)==str(raw['Estate_ID'].iloc[0])).all(),
              'Block metadata Estate_ID differs from current daily inputs')
        _need(np.isfinite(metadata[STATS].apply(pd.to_numeric, errors='coerce').to_numpy()).all(),
              'Grid positions and relative vulnerability require actual numeric values')
        edges = pd.read_csv(edges_path, encoding='utf-8-sig')
        _need({'Source_Block','Target_Block'}.issubset(edges.columns),
              'Adjacency CSV requires Source_Block and Target_Block')
        _need(not edges.duplicated(['Source_Block','Target_Block']).any(), 'Adjacency contains duplicate links')
        _need(edges['Source_Block'].isin(BLOCKS).all() and edges['Target_Block'].isin(BLOCKS).all(),
              'Adjacency references an unknown block')
        _need((edges['Source_Block']!=edges['Target_Block']).all(), 'Adjacency self-links are invalid')
        _need(set(edges['Target_Block'])==set(BLOCKS), 'Each block must have at least one incoming adjacency')
    except CurrentDataUnavailable:
        raise
    except (ValueError, TypeError, KeyError, OSError, pd.errors.ParserError) as exc:
        raise CurrentDataUnavailable(f'Current-date input contract could not be validated: {type(exc).__name__}: {exc}') from exc
    return {'source_rows': int(len(raw)), 'source_dates': [str(min(wanted)),str(max(wanted))],
            'inspected_records':int(len(observed)), 'blocks':16, 'diseases':4}


def current_readiness(root=ROOT):
    today=sri_lanka_today()
    paths=current_paths(root)
    out={'today_date':today.isoformat(), 'forecast_first_date':(today+timedelta(days=1)).isoformat(),
         'forecast_last_date':(today+timedelta(days=7)).isoformat(),
         'required_history_from':(today-timedelta(days=20)).isoformat(),
         'required_history_through':today.isoformat(),
         'required_files':{str(path.relative_to(Path(root).resolve())):path.is_file() for path in paths},
         'ready':False,'field_model_validated':False}
    try:
        out['input_validation']=validate_current_data(root,today)
        out['ready']=True
    except CurrentDataUnavailable as e:
        out['missing_or_invalid_data']=str(e)
    return out


def _read_previous_today(root, origin:date):
    path=Path(root)/CURRENT_OBSERVATIONS_CSV
    if not path.is_file():
        return []
    try:
        df=pd.read_csv(path, encoding='utf-8-sig', keep_default_na=False)
        _need(list(df.columns)==CSV_FIELDS, 'Current observations storage schema mismatch')
        records=[]
        for row in df.to_dict('records'):
            if row['forecast_origin_date'] != origin.isoformat():
                continue
            records.append(validate_observation(row['block_id'],row['disease_name'],
                                                 int(row['inspected_bushes']),int(row['symptomatic_bushes'])))
        return records
    except (ValueError, KeyError, OSError) as e:
        raise CurrentDataUnavailable(f'Cannot read officer observations: {e}') from e


def _atomic_write_csv(path, df):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='step51_',suffix='.csv',dir=path.parent)
    os.close(fd)
    try:
        df.to_csv(tmp,index=False)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def _atomic_write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='step51_',suffix='.json',dir=path.parent)
    os.close(fd)
    try:
        Path(tmp).write_text(json.dumps(data,indent=2,allow_nan=False),encoding='utf-8')
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def current_dynamic_predict(root, block_id, disease_name, inspected_bushes, symptomatic_bushes,
                            *, save=False, predictor=None):
    """Forecast next 7 calendar days only when 21 actual current-date input days exist.

    The existing preprocessor & trained model are re-used without refitting.
    Current-date input is not a guarantee of model generalization to real estates.
    """
    root=Path(root).resolve()
    obs=validate_observation(block_id,disease_name,inspected_bushes,symptomatic_bushes)
    origin=sri_lanka_today()
    with _LOCK:
        validated=validate_current_data(root,origin)
        source_path,block_path,edges_path=current_paths(root)
        earlier=_read_previous_today(root,origin)
        try:
            built=prepare_24h_inputs(root,origin,earlier+[obs],
                source_csv=source_path,blocks_csv=block_path,adjacency_csv=edges_path)
            scaled,tabular=arrays_for_disease(built,disease_name)
            if predictor is None:
                from selected_spread_inference import SelectedSpreadPredictor
                predictor=SelectedSpreadPredictor(root, threads=2)
            predictions=predictor.predict_disease(disease_name,scaled,tabular)
        except (ValueError,KeyError,FileNotFoundError,RuntimeError,OSError) as exc:
            raise CurrentDataUnavailable(f'Current model inputs/checkpoints unavailable: {type(exc).__name__}: {exc}') from exc
        _need(len(predictions)==16*7,'Model did not return predictions for 16 blocks x 7 days')
        all_days=[]
        for r in predictions:
            p=dict(r)
            _need(p['block_id'] in BLOCKS and 1 <= int(p['horizon_day']) <= 7, 'Bad model block/day')
            p.update(forecast_origin_date=origin.isoformat(),
                     forecast_target_date=(origin+timedelta(days=int(p['horizon_day']))).isoformat(),
                     data_provenance='RECENT_USER_SUPPLIED_DATA_NOT_INDEPENDENTLY_VERIFIED')
            all_days.append(p)
        chosen=[r for r in all_days if r['block_id']==block_id]
        _need(len(chosen)==7 and {int(r['horizon_day']) for r in chosen}==set(range(1,8)),
              'Incomplete forecast horizons')
        result={
            'schema_version':'step51-current-date-v1',
            'forecast_origin_date':origin.isoformat(),
            'selected_block_id':block_id,'disease_name':disease_name,
            'submitted_observation':obs,
            'forecast_target_start':(origin+timedelta(days=1)).isoformat(),
            'forecast_target_end':(origin+timedelta(days=7)).isoformat(),
            'source_data_check':validated,
            'model_trained_on_synthetic_data':True,
            'field_validated':False,
            'independent_current_period_validation_completed':False,
            'selected_block_daily_forecast':chosen,
            'all_block_forecast_for_selected_disease':all_days,
            'warning':'Current-dated inference using recent supplied inputs; trained model has not been independently evaluated on real current estate data. Do not treat as verified disease transmission or spraying advice.',
            'saved':False,
        }
        if save:
            path=root/CURRENT_OBSERVATIONS_CSV
            if path.exists():
                df=pd.read_csv(path,encoding='utf-8-sig')
                _need(list(df.columns)==CSV_FIELDS,'Current observations CSV schema mismatch')
            else:
                df=pd.DataFrame(columns=CSV_FIELDS)
            saved_row={**obs,'observation_id':uuid.uuid4().hex,'forecast_origin_date':origin.isoformat(),
                       'created_at_utc':datetime.now(timezone.utc).isoformat()}
            incoming=pd.DataFrame([saved_row],columns=CSV_FIELDS)
            df=(incoming if df.empty else pd.concat([df,incoming],ignore_index=True))[CSV_FIELDS]
            _atomic_write_csv(path,df)
            result['saved']=True
            _atomic_write_json(root/CURRENT_LATEST_JSON,result)
        return result


def current_latest(root=ROOT):
    path=Path(root)/CURRENT_LATEST_JSON
    if not path.is_file():
        raise CurrentDataUnavailable('No saved current-date forecast')
    try:
        data=json.loads(path.read_text(encoding='utf-8'))
        _need(data.get('schema_version')=='step51-current-date-v1', 'Saved forecast contract mismatch')
        _need(data.get('forecast_origin_date')==sri_lanka_today().isoformat(),
              'Saved forecast is from a previous day; generate a new one')
        return data
    except (OSError,ValueError,KeyError) as e:
        raise CurrentDataUnavailable(f'Saved current-date forecast unreadable: {e}') from e


def current_observations(root=ROOT,limit=30):
    path=Path(root)/CURRENT_OBSERVATIONS_CSV
    if not path.is_file():
        return {'records':[],'count':0}
    try:
        df=pd.read_csv(path,encoding='utf-8-sig',keep_default_na=False)
        _need(list(df.columns)==CSV_FIELDS, 'Current observations CSV schema mismatch')
        return {'records':df.tail(limit).iloc[::-1].to_dict('records'),'count':len(df)}
    except (OSError,ValueError,KeyError) as e:
        raise CurrentDataUnavailable(f'Current observation storage error: {e}') from e
