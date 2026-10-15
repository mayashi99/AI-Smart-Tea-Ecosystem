#!/usr/bin/env python3
"""Read-only Step41 historical simulation rule-alert service for frontend API adapter.

A new observation submission MUST NOT call this service and claim dynamic inference.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BLOCKS=tuple(f'B{i:02d}' for i in range(1,17))
DISEASES=('Brown Blight','Grey Leaf','Red Rust','Red Spider Mite')


def load_alerts(root=ROOT):
    p=Path(root)/'outputs/dashboard/m05/step41_historical_alerts.json'
    if not p.is_file(): raise FileNotFoundError(f'Run Step41 first: {p}')
    data=json.loads(p.read_text(encoding='utf-8'))
    if data.get('schema_version')!='step41-m05-historical-rule-alerts-v1':
        raise ValueError('Unrecognized Step41 alert schema')
    m=data['metadata']
    if m.get('mode')!='HISTORICAL_SIMULATION_NOT_LIVE' or m.get('is_live_prediction') is not False:
        raise ValueError('Step41 must be historical/non-live')
    return data


def get_alert_overview(root=ROOT):
    a=load_alerts(root)
    return {'metadata':a['metadata'],'summary':a['summary'],'block_summaries':a['block_summaries'],
            'rules':a['rules'],'warnings':a['warnings']}


def get_block_alerts(root=ROOT, block_id='B01', disease=None):
    if block_id not in BLOCKS: raise ValueError('Invalid block: choose B01–B16')
    if disease is not None and disease not in DISEASES: raise ValueError(f'Invalid disease: {disease!r}')
    a=load_alerts(root)
    a1=[r for r in a['block_disease_alerts'] if r['block_id']==block_id and (disease is None or r['disease_name']==disease)]
    a2=[r for r in a['daily_triage'] if r['block_id']==block_id and (disease is None or r['disease_name']==disease)]
    n=1 if disease else 4
    if len(a1)!=n or len(a2)!=n*7: raise ValueError('Incomplete Step41 block-level records')
    return {'block_id':block_id,'disease':disease,'origin_date':a['metadata']['forecast_origin_date'],
            'mode':a['metadata']['mode'],'is_live':False,
            'block_disease_alerts':a1,'daily_explanations':a2,
            'warning':'Read-only historical demonstration. New officer inputs do NOT affect these values.'}


def get_daily_rationale(root=ROOT, block_id='B01', disease='Red Rust', horizon_day=1):
    if type(horizon_day) is not int or horizon_day not in range(1,8):
        raise ValueError('horizon_day must be integer 1..7')
    res=get_block_alerts(root,block_id,disease)
    rows=[r for r in res['daily_explanations'] if r['horizon_day']==horizon_day]
    if len(rows)!=1: raise ValueError('Missing/duplicate daily rationale')
    return rows[0]
