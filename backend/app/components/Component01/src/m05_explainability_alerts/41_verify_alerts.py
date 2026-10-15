#!/usr/bin/env python3
"""Audit every historical block/disease/horizon plus rule decision consistency."""
from __future__ import annotations
import json
from pathlib import Path
from m05_alert_service import BLOCKS,DISEASES,load_alerts,get_alert_overview,get_block_alerts,get_daily_rationale
from importlib.machinery import SourceFileLoader

ROOT=Path(__file__).resolve().parents[2]
script=SourceFileLoader('step41build',str(Path(__file__).parent/'41_generate_simulation_alerts.py')).load_module()


def run():
    a=load_alerts(ROOT)
    assert len(a['daily_triage'])==448 and len(a['block_disease_alerts'])==64
    assert len(a['block_summaries'])==16
    assert a['metadata']['new_observation_reforecast_supported_here'] is False
    assert a['metadata']['explanation_type']=='RULE_RATIONALE_ONLY_NOT_MODEL_XAI'
    checked=0
    for b in BLOCKS:
        all_d=get_block_alerts(ROOT,b)
        assert len(all_d['block_disease_alerts'])==4 and len(all_d['daily_explanations'])==28
        for d in DISEASES:
            x=get_block_alerts(ROOT,b,d)
            assert len(x['block_disease_alerts'])==1 and len(x['daily_explanations'])==7
            for h in range(1,8):
                r=get_daily_rationale(ROOT,b,d,h)
                expected,triggers=script.level_and_triggers(r['incidence_percent_prediction'],r['activity_predicted_class'],r['new_onset_predicted_class'])
                assert r['demo_alert_level']==expected and r['trigger_codes']==triggers
                assert r['simulation_only'] and not r['is_live_prediction']
                assert r['explanation_type']=='TRANSPARENT_RULE_RATIONALE_NOT_MODEL_ATTRIBUTION'
                checked+=1
    for args in [dict(block_id='B00'),dict(block_id='B17'),dict(block_id='B01',disease='Healthy')]:
        try: get_block_alerts(ROOT,**args)
        except ValueError: pass
        else: raise AssertionError(f'Invalid accepted: {args}')
    for day in [0,8,1.0,'1',True]:
        try: get_daily_rationale(ROOT,'B01','Red Rust',day)
        except ValueError: pass
        else: raise AssertionError(f'Invalid horizon accepted: {day}')
    assert get_alert_overview(ROOT)['summary']['daily_rows']==448
    print('='*78)
    print('STEP41 VERIFY - PASS')
    print(f'Checked {checked}/448 daily rule decisions, 64/64 block-disease groups, all 16 block cards.')
    print('All invalid block/disease/horizon selections rejected. No live/XAI mislabelling.')
    print('NOTICE: rule explanations ONLY; not SHAP or Grad-CAM++. Historical simulation, not dynamic.')

if __name__=='__main__':run()
