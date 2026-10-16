"""Step43 FastAPI facade over verified Steps 40, 41 and 42.

LOCAL SINGLE-WORKER HISTORICAL SIMULATION. It does not make current-date
forecasts, train models, or require a database. Use uvicorn ... --workers 1.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, StrictInt

ROOT = Path(__file__).resolve().parents[1]
for rel in ('src/m04_disease_spread', 'src/m03_severity_climate', 'src/m05_explainability_alerts'):
    loc = str(ROOT / rel)
    if loc not in sys.path:
        sys.path.insert(0, loc)

from dynamic_spread_service import (
    BLOCKS, DISEASES, CSV_FIELDS, dynamic_predict, origin_from_snapshot,
    runtime_file, validate_observation,
)
from m03_dashboard_service import (
    get_overview, get_block_dashboard, get_climate_history,
)
from m05_alert_service import get_alert_overview, get_block_alerts, get_daily_rationale

DESCRIPTION = (
    'Simulation prototype: Steps 40/41 provide READ-ONLY historical dashboard data; '
    'Step42 performs actual saved-model inference using officer-overlaid historical inputs. '
    'All forecasts are anchored to a historical 2025 origin and synthetic blocks. '
    'Not a live estate deployment, not a validated climate point, not medical/agricultural advice.'
)
app = FastAPI(title='Tea Disease Intelligence — Component01 Demo API',
              description=DESCRIPTION, version='0.43.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:5173','http://127.0.0.1:5173',
                   'http://localhost:3000','http://127.0.0.1:3000'],
    allow_credentials=False,allow_methods=['GET','POST'],allow_headers=['*'],
)


class OfficerObservation(BaseModel):
    block_id: str = Field(..., examples=['B06'])
    disease: str = Field(..., examples=['Red Rust'])
    inspected_bushes: StrictInt = Field(..., ge=1, le=1_000_000)
    symptomatic_bushes: StrictInt = Field(..., ge=0)


class IncidenceRequest(OfficerObservation):
    pass


def _handle_value_error(error: ValueError):
    raise HTTPException(status_code=422, detail=str(error)) from error


def _handle_data_error(error: Exception):
    # Fail closed on absent/mismatched prerequisites; never invent response data.
    raise HTTPException(status_code=503, detail=f'Component demo data unavailable: {type(error).__name__}: {error}') from error


def _check(block_id: str, disease: Optional[str] = None):
    if block_id not in BLOCKS:
        raise HTTPException(422, 'Invalid block_id. Choose B01..B16.')
    if disease is not None and disease not in DISEASES:
        raise HTTPException(422, f'Invalid disease. Choose one of: {", ".join(DISEASES)}')


def _predict(payload: OfficerObservation, save: bool):
    try:
        return dynamic_predict(ROOT, payload.block_id, payload.disease,
                               payload.inspected_bushes, payload.symptomatic_bushes,
                               save=save)
    except ValueError as e:
        _handle_value_error(e)
    except (FileNotFoundError, KeyError, OSError, ImportError) as e:
        _handle_data_error(e)


@app.get('/')
def root():
    return {'service':'Component01 Tea Disease Demo API','docs':'/docs',
            'mode':'HISTORICAL_SYNTHETIC_SIMULATION_NOT_LIVE'}


@app.get('/health')
def health():
    checks = {
        'step32_snapshot': (ROOT/'outputs/dashboard/spread/step32_validation_snapshot_metadata.json').is_file(),
        'step40_dashboard': (ROOT/'outputs/dashboard/m03/step40_historical_dashboard.json').is_file(),
        'step41_alerts': (ROOT/'outputs/dashboard/m05/step41_historical_alerts.json').is_file(),
        'step42_source': (ROOT/'src/m04_disease_spread/dynamic_spread_service.py').is_file(),
    }
    return {'status': 'ready' if all(checks.values()) else 'missing_prerequisites',
            'checks':checks,'simulation_only':True,
            'note':'Readiness does not independently prove model checkpoint availability.'}


@app.get('/api/estate/blocks')
def list_blocks():
    return {'blocks':[{'block_id':b} for b in BLOCKS], 'count':len(BLOCKS), 'synthetic':True}


@app.get('/api/estate/diseases')
def list_diseases():
    return {'diseases':DISEASES,'count':len(DISEASES),'healthy_not_forecast_as_disease':True}


@app.get('/api/metadata')
def metadata():
    try:
        origin=origin_from_snapshot(ROOT)
    except (ValueError, KeyError, FileNotFoundError, OSError) as e:
        _handle_data_error(e)
    return {'forecast_origin_date':origin.isoformat(),
            'mode':'OFFICER_CONDITIONED_HISTORICAL_VALIDATION_SIMULATION',
            'live_forecast':False,'data_source':'simulated estate + unverified single-point NASA climate',
            'blocks':len(BLOCKS),'diseases':DISEASES,'forecast_horizons_days':list(range(1,8)),
            'observation_storage':'local CSV single process',
            'image_cnn_full_training_ready':False}


@app.post('/api/severity/incidence')
def calculate_incidence(payload: IncidenceRequest):
    try:
        result=validate_observation(payload.block_id,payload.disease,
                                   payload.inspected_bushes,payload.symptomatic_bushes)
    except ValueError as e:
        _handle_value_error(e)
    return {**result,'metric':'sampled_bush_disease_incidence_percent',
            'leaf_lesion_area_severity':None,'warning':'Incidence is not image lesion-area severity.'}


@app.get('/api/dashboard/historical/overview')
def dashboard_overview():
    try: return get_overview(ROOT)
    except (FileNotFoundError,ValueError,KeyError) as e: _handle_data_error(e)


@app.get('/api/dashboard/historical/blocks/{block_id}')
def dashboard_block(block_id: str, disease: Optional[str] = None):
    _check(block_id,disease)
    try: return get_block_dashboard(ROOT,block_id,disease)
    except (FileNotFoundError,ValueError,KeyError) as e: _handle_data_error(e)


@app.get('/api/dashboard/historical/climate')
def climate_history(limit: int=Query(12,ge=1,le=240)):
    try: return get_climate_history(ROOT,limit)
    except (FileNotFoundError,ValueError,KeyError) as e: _handle_data_error(e)


@app.get('/api/alerts/historical/overview')
def alerts_overview():
    try: return get_alert_overview(ROOT)
    except (FileNotFoundError,ValueError,KeyError) as e: _handle_data_error(e)


@app.get('/api/alerts/historical/blocks/{block_id}')
def alerts_block(block_id: str, disease: Optional[str]=None):
    _check(block_id,disease)
    try: return get_block_alerts(ROOT,block_id,disease)
    except (FileNotFoundError,ValueError,KeyError) as e: _handle_data_error(e)


@app.get('/api/alerts/historical/blocks/{block_id}/days/{horizon_day}')
def alert_day(block_id:str,horizon_day:int,disease:str=Query(...)):
    _check(block_id,disease)
    if not 1<=horizon_day<=7: raise HTTPException(422, 'horizon_day must be 1..7')
    try: return get_daily_rationale(ROOT,block_id,disease,horizon_day)
    except (FileNotFoundError,ValueError,KeyError) as e: _handle_data_error(e)


@app.post('/api/forecast/preview')
def forecast_preview(payload:OfficerObservation):
    """Real Step42 model execution without persisting an observation."""
    return _predict(payload, save=False)


@app.post('/api/forecast/recalculate')
def forecast_recalculate(payload:OfficerObservation):
    """Run actual model inference, then atomically persist officer input + latest JSON."""
    return _predict(payload, save=True)


@app.get('/api/observations')
def observations(block_id:Optional[str]=None, disease:Optional[str]=None,
                 limit:int=Query(30,ge=1,le=500)):
    if block_id is not None or disease is not None:
        if block_id is not None: _check(block_id,disease)
        elif disease not in DISEASES: raise HTTPException(422,'Invalid disease')
    p=runtime_file(ROOT)
    if not p.exists():
        return {'records':[],'count':0,'storage':'CSV','simulation_only':True}
    try:
        df=pd.read_csv(p,encoding='utf-8-sig',keep_default_na=False)
        if list(df.columns)!=CSV_FIELDS: raise ValueError('Runtime schema mismatch')
        if block_id: df=df.loc[df.block_id.eq(block_id)]
        if disease: df=df.loc[df.disease_name.eq(disease)]
        total=len(df)
        rows=df.tail(limit).iloc[::-1].to_dict('records')
        return {'records':rows,'count':total,'storage':'CSV','simulation_only':True}
    except (ValueError,OSError) as e: _handle_data_error(e)


@app.get('/api/forecast/latest')
def latest_forecast(block_id:Optional[str]=None,disease:Optional[str]=None):
    if block_id is not None: _check(block_id,disease)
    elif disease is not None and disease not in DISEASES: raise HTTPException(422,'Invalid disease')
    p=ROOT/'outputs/dashboard/dynamic/step42_latest_officer_forecast.json'
    if not p.is_file(): raise HTTPException(404,'No previously SAVED dynamic forecast. POST /api/forecast/recalculate first.')
    try:
        record=json.loads(p.read_text(encoding='utf-8'))
    except (ValueError,OSError) as e: _handle_data_error(e)
    if not record.get('actual_saved_model_inference') or record.get('is_current_live_estate_forecast') is not False:
        raise HTTPException(503,'Invalid saved simulation forecast metadata')
    if block_id is not None and record.get('selected_block_id')!=block_id:
        raise HTTPException(404,'Latest saved forecast is for another block; POST recalculate for this block.')
    if disease is not None and record.get('disease_name')!=disease:
        raise HTTPException(404,'Latest saved forecast is for another disease; POST recalculate for this disease.')
    return record


# Step51: additive current-date forecast API. Historical endpoints remain unchanged.
from step51_current_spread_service import (
    current_readiness, current_dynamic_predict, current_observations, current_latest,
    CurrentDataUnavailable,
)

@app.get('/api/forecast/current/status', tags=['Current-date forecasts'])
def current_forecast_status():
    return current_readiness(ROOT)

@app.post('/api/forecast/current/preview', tags=['Current-date forecasts'])
def current_forecast_preview(payload: OfficerObservation):
    try:
        return current_dynamic_predict(ROOT, payload.block_id, payload.disease,
                                       payload.inspected_bushes, payload.symptomatic_bushes, save=False)
    except ValueError as e:
        _handle_value_error(e)
    except (CurrentDataUnavailable, FileNotFoundError, KeyError, OSError, ImportError) as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

@app.post('/api/forecast/current/recalculate', tags=['Current-date forecasts'])
def current_forecast_recalculate(payload: OfficerObservation):
    try:
        return current_dynamic_predict(ROOT, payload.block_id, payload.disease,
                                       payload.inspected_bushes, payload.symptomatic_bushes, save=True)
    except ValueError as e:
        _handle_value_error(e)
    except (CurrentDataUnavailable, FileNotFoundError, KeyError, OSError, ImportError) as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

@app.get('/api/forecast/current/latest', tags=['Current-date forecasts'])
def current_forecast_latest():
    try:
        return current_latest(ROOT)
    except CurrentDataUnavailable as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

@app.get('/api/forecast/current/observations', tags=['Current-date forecasts'])
def current_forecast_observations(limit: int=Query(30, ge=1, le=500)):
    try:
        return current_observations(ROOT, limit=limit)
    except CurrentDataUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

# Step52: today's inspection with historical same-season context; no new data-file requirement.
from step52_seasonal_context_service import (
    seasonal_status, seasonal_predict, seasonal_latest, seasonal_observations,
    SeasonalContextUnavailable,
)

@app.get('/api/forecast/assisted/status', tags=['Seven-day seasonal-context forecast'])
def assisted_forecast_status():
    return seasonal_status(ROOT)

@app.post('/api/forecast/assisted/preview', tags=['Seven-day seasonal-context forecast'])
def assisted_forecast_preview(payload: OfficerObservation):
    try:
        return seasonal_predict(ROOT, payload.block_id, payload.disease,
                                payload.inspected_bushes, payload.symptomatic_bushes, save=False)
    except ValueError as exc:
        _handle_value_error(exc)
    except SeasonalContextUnavailable as exc:
        raise HTTPException(503, detail=str(exc)) from exc

@app.post('/api/forecast/assisted/recalculate', tags=['Seven-day seasonal-context forecast'])
def assisted_forecast_recalculate(payload: OfficerObservation):
    try:
        return seasonal_predict(ROOT, payload.block_id, payload.disease,
                                payload.inspected_bushes, payload.symptomatic_bushes, save=True)
    except ValueError as exc:
        _handle_value_error(exc)
    except SeasonalContextUnavailable as exc:
        raise HTTPException(503, detail=str(exc)) from exc

@app.get('/api/forecast/assisted/latest', tags=['Seven-day seasonal-context forecast'])
def assisted_forecast_latest():
    try:
        return seasonal_latest(ROOT)
    except SeasonalContextUnavailable as exc:
        raise HTTPException(404, detail=str(exc)) from exc

@app.get('/api/forecast/assisted/observations', tags=['Seven-day seasonal-context forecast'])
def assisted_forecast_observations(limit:int=Query(30,ge=1,le=500)):
    try:
        return seasonal_observations(ROOT,limit=limit)
    except SeasonalContextUnavailable as exc:
        raise HTTPException(503, detail=str(exc)) from exc
