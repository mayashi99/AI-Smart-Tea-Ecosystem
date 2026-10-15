#!/usr/bin/env python3
"""Read-only Step40 historical dashboard data service for future FastAPI routes.

DOES NOT accept/save observations or regenerate a model forecast.
"""
from __future__ import annotations
import json
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2]
DISEASES = ('Brown Blight','Grey Leaf','Red Rust','Red Spider Mite')
BLOCKS = tuple(f'B{i:02d}' for i in range(1,17))


def load_dashboard(component_root=DEFAULT_ROOT):
    p = Path(component_root)/'outputs/dashboard/m03/step40_historical_dashboard.json'
    if not p.is_file():
        raise FileNotFoundError(f'Run Step40 first: {p}')
    data = json.loads(p.read_text(encoding='utf-8'))
    if data.get('schema_version')!='step40-m03-dashboard-v1':
        raise ValueError('Unexpected Step40 dashboard schema.')
    if data['metadata']['dynamic_observation_reforecast_available'] is not False:
        raise ValueError('Step40 data must be explicitly historical/non-live.')
    return data


def get_overview(component_root=DEFAULT_ROOT):
    data=load_dashboard(component_root)
    return {'metadata':data['metadata'], 'summary':data['summary'], 'warnings':data['warnings']}


def get_block_dashboard(component_root=DEFAULT_ROOT, block_id='B01', disease=None):
    if block_id not in BLOCKS:
        raise ValueError(f'Invalid block_id {block_id!r}. Expected B01–B16.')
    if disease is not None and disease not in DISEASES:
        raise ValueError(f'Invalid disease {disease!r}. Expected one of {DISEASES}.')
    data=load_dashboard(component_root)
    def matching(row):
        return row['block_id']==block_id and (disease is None or row['disease_name']==disease)
    ctx=[r for r in data['block_disease_context'] if matching(r)]
    forecast=[r for r in data['seven_day_spread_forecasts'] if matching(r)]
    expect_context=4 if disease is None else 1
    if len(ctx)!=expect_context or len(forecast)!=expect_context*7:
        raise ValueError('Incomplete block/disease predictions in Step40 historical data.')
    return {'block_id':block_id,'disease':disease,'forecast_origin_date':data['metadata']['forecast_origin_date'],
            'mode':data['metadata']['mode'],'is_live':False,
            'climate_context':data['metadata']['historical_climate_last_7d'],
            'block_disease_context':ctx,'seven_day_spread_forecasts':forecast,
            'warning':'Historical validation simulation. New inputs DO NOT update this snapshot.'}


def get_climate_history(component_root=DEFAULT_ROOT, limit=12):
    if not isinstance(limit,int) or not (1<=limit<=240):
        raise ValueError('limit must be integer between 1 and 240')
    data=load_dashboard(component_root)
    return {'origin_date':data['metadata']['forecast_origin_date'],
            'mode':data['metadata']['mode'],'monthly_records':data['climate_monthly_history'][-limit:],
            'warning':'Only full months STRICTLY before forecast-origin month; single point not estate matched.'}
