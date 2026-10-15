#!/usr/bin/env python3
"""Step41: historical simulation alert-rule explanations, NOT model feature attributions.

Uses Step40 historical validation predictions. No trained models are invoked here;
never confuse with live officer-conditioned forecasting or empirically calibrated alerts.
"""
from __future__ import annotations
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INPUT = Path('outputs/dashboard/m03/step40_historical_seven_day_integrated.csv')
INPUT_CONTRACT = Path('outputs/dashboard/m03/step40_dashboard_contract.json')
OUT = Path('outputs/dashboard/m05')
REPORT = Path('outputs/reports/step41_m05_alert_audit.json')
DISEASES = ('Brown Blight', 'Grey Leaf', 'Red Rust', 'Red Spider Mite')
BLOCKS = tuple(f'B{i:02d}' for i in range(1, 17))
DAYS = tuple(range(1, 8))
LEVEL_ORDER = {'DEMO_INFO':0, 'DEMO_WATCH':1, 'DEMO_HIGH':2}

# Illustrative trigger bands, not assessed/approved agronomic action thresholds.
RULES = {
    'high_if_predicted_incidence_pct_at_least': 15.0,
    'watch_if_predicted_incidence_pct_at_least': 5.0,
    'high_if_activity_and_new_onset_classes_both_positive': True,
    'watch_if_either_predicted_class_positive': True,
    'severity_definitions': {
        'DEMO_HIGH': 'Illustrative priority for prompt officer review, NOT a validated agronomic threshold',
        'DEMO_WATCH': 'Illustrative inspection priority, NOT a validated agronomic threshold',
        'DEMO_INFO': 'No configured illustrative alert trigger on this day; NOT an assurance of disease absence',
    },
    'recommended_officer_action': {
        'DEMO_HIGH': 'Review this simulated block promptly; inspect affected plants, verify field observations, and consult a qualified tea agronomist before treatment decisions.',
        'DEMO_WATCH': 'Schedule a follow-up field inspection; confirm symptomatic bush counts and record new observations.',
        'DEMO_INFO': 'Continue scheduled observation and record any symptoms; this simulated output does not verify disease absence.',
    },
}

REQUIRED = (
  'forecast_origin_date', 'forecast_target_date', 'record_type', 'data_provenance',
  'block_id', 'disease_name', 'horizon_day', 'activity_predicted_class',
  'new_onset_predicted_class', 'incidence_percent_prediction',
  'activity_probability_uncalibrated', 'new_onset_probability_uncalibrated',
  'activity_family', 'incidence_family', 'onset_family',
  'sample_incidence_pct','inspected_bushes','symptomatic_bushes',
  'climate_background_activity_model','climate_background_onset_model',
  'historical_7d_rainfall_total_mm','historical_7d_temp_mean_c',
  'simulation_only','is_live_prediction','leaf_lesion_area_pct',
)


def fail(msg):
    raise ValueError('Step41 input-contract error: '+msg)


def truth(v):
    return str(v).strip().lower() in ('true','1','yes')


def number(v, field, low, high):
    try:
        val=float(v)
    except (ValueError,TypeError):
        fail(f'{field} not numeric: {v!r}')
    if not math.isfinite(val) or not low<=val<=high:
        fail(f'{field} out of range [{low}, {high}]: {v!r}')
    return val


def binary(v, field):
    n=number(v,field,0,1)
    if n not in (0,1): fail(f'{field} must be binary')
    return int(n)


def sha256(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()


def level_and_triggers(incidence,active,onset):
    high = incidence >= RULES['high_if_predicted_incidence_pct_at_least'] or (active==1 and onset==1)
    watch = incidence >= RULES['watch_if_predicted_incidence_pct_at_least'] or active==1 or onset==1
    triggers=[]
    if incidence>=15: triggers.append('predicted_incidence_at_least_15_percent')
    elif incidence>=5: triggers.append('predicted_incidence_at_least_5_percent')
    if active: triggers.append('model_activity_class_positive')
    if onset: triggers.append('model_new_onset_class_positive')
    if active and onset: triggers.append('both_predicted_classes_positive')
    return ('DEMO_HIGH' if high else 'DEMO_WATCH' if watch else 'DEMO_INFO'),triggers


def run(root=ROOT):
    root=Path(root)
    source=root/INPUT
    contract_p=root/INPUT_CONTRACT
    if not source.is_file() or not contract_p.is_file():
        raise FileNotFoundError('Run Step40 first; expected Step40 integrated CSV and contract.')
    contract=json.loads(contract_p.read_text(encoding='utf-8'))
    if contract.get('frontend_mode')!='HISTORICAL_SIMULATION_DEMO_ONLY' or contract.get('dynamic_predictions_implemented_here') is not False:
        fail('Step40 contract must explicitly be historical/non-dynamic')
    hash_before=sha256(source)
    daily=[]; seen=set(); origins=set()
    with source.open('r',encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        missing=set(REQUIRED)-set(reader.fieldnames or [])
        if missing: fail(f'missing columns: {sorted(missing)}')
        for row in reader:
            b=row['block_id']; d=row['disease_name']
            h=int(number(row['horizon_day'],'horizon_day',1,7))
            if b not in BLOCKS or d not in DISEASES: fail(f'bad block/disease: {b}, {d}')
            k=(b,d,h)
            if k in seen: fail(f'duplicate key {k}')
            seen.add(k)
            if not truth(row['simulation_only']) or truth(row['is_live_prediction']):
                fail('input is not marked as historical simulation')
            if 'SIMULATION' not in row['data_provenance'] or 'HISTORICAL_VALIDATION' not in row['record_type']:
                fail('input provenance is not historical simulation')
            if row['leaf_lesion_area_pct'].strip():
                fail('this dashboard must not invent lesion-area measurement')
            origin=date.fromisoformat(row['forecast_origin_date']); target=date.fromisoformat(row['forecast_target_date'])
            if target != origin+timedelta(days=h): fail(f'target-date mismatch {k}')
            origins.add(origin.isoformat())
            incidence=number(row['incidence_percent_prediction'],'incidence_percent_prediction',0,100)
            active=binary(row['activity_predicted_class'],'activity_predicted_class')
            onset=binary(row['new_onset_predicted_class'],'new_onset_predicted_class')
            activity_score=number(row['activity_probability_uncalibrated'],'activity_probability_uncalibrated',0,1)
            onset_score=number(row['new_onset_probability_uncalibrated'],'new_onset_probability_uncalibrated',0,1)
            sample=number(row['sample_incidence_pct'],'sample_incidence_pct',0,100)
            inspected=number(row['inspected_bushes'],'inspected_bushes',0,100000000)
            symptomatic=number(row['symptomatic_bushes'],'symptomatic_bushes',0,100000000)
            if inspected<=0 or symptomatic>inspected or abs(100*symptomatic/inspected-sample)>.011:
                fail(f'officer historical sample inconsistent at {k}')
            lvl,triggers=level_and_triggers(incidence,active,onset)
            explanation = [
                f'Saved Step40 {h}-day historical SIMULATION forecast has predicted sampled-bush incidence {incidence:.2f}%.',
                f'Saved model activity class={active}; new-onset class={onset}.',
                f'Demo triage: {lvl} because '+(', '.join(triggers) if triggers else 'no configured trigger fired')+'.',
                f'Last synthetic inspection was {int(inspected)} bushes with {int(symptomatic)} symptomatic ({sample:.2f}% observed simulated sample incidence).',
                'Seven-day historical NASA climate is descriptive context, NOT proven cause or block-specific attribution.',
            ]
            daily.append({
                'forecast_origin_date':origin.isoformat(),'forecast_target_date':target.isoformat(),
                'block_id':b,'disease_name':d,'horizon_day':h,
                'demo_alert_level':lvl,'trigger_codes':triggers,
                'incidence_percent_prediction':round(incidence,5),
                'activity_predicted_class':active,'new_onset_predicted_class':onset,
                'activity_score_uncalibrated':round(activity_score,6),
                'onset_score_uncalibrated':round(onset_score,6),
                'activity_family':row['activity_family'],
                'incidence_family':row['incidence_family'],
                'onset_family':row['onset_family'],
                'last_simulated_sample_incidence_pct':round(sample,4),
                'historical_7d_rainfall_mm':round(number(row['historical_7d_rainfall_total_mm'],'rainfall',0,100000),4),
                'historical_7d_mean_temperature_c':round(number(row['historical_7d_temp_mean_c'],'temp',-100,100),4),
                'climate_model_is_weather_based':False,
                'climate_background_model':row['climate_background_activity_model'],
                'explanation_type':'TRANSPARENT_RULE_RATIONALE_NOT_MODEL_ATTRIBUTION',
                'rule_explanation':explanation,
                'recommended_officer_action':RULES['recommended_officer_action'][lvl],
                'simulation_only':True,'is_live_prediction':False,
                'is_leaf_lesion_area_severity':False,
            })
    if len(daily)!=448 or len(seen)!=448 or len(origins)!=1:
        fail(f'expected 448 keys and 1 origin; got {len(daily)}, {len(seen)}, {origins}')
    if seen!={(b,d,h) for b in BLOCKS for d in DISEASES for h in DAYS}:
        fail('not all 16 x 4 x 7 combinations present')
    daily.sort(key=lambda z:(z['block_id'],z['disease_name'],z['horizon_day']))
    grouped=defaultdict(list)
    for r in daily: grouped[(r['block_id'],r['disease_name'])].append(r)
    block_disease=[]
    for b in BLOCKS:
        for d in DISEASES:
            rows=grouped[(b,d)]
            peak=max(rows,key=lambda x:x['incidence_percent_prediction'])
            level=max((r['demo_alert_level'] for r in rows),key=lambda x:LEVEL_ORDER[x])
            first=next((r['horizon_day'] for r in rows if LEVEL_ORDER[r['demo_alert_level']]>=1),None)
            active_days=[r['horizon_day'] for r in rows if r['activity_predicted_class']==1]
            onset_days=[r['horizon_day'] for r in rows if r['new_onset_predicted_class']==1]
            entry={
                'block_id':b,'disease_name':d,'forecast_origin_date':next(iter(origins)),
                'seven_day_overall_demo_level':level,
                'first_alert_day':first,'peak_predicted_incidence_pct':peak['incidence_percent_prediction'],
                'peak_incidence_day':peak['horizon_day'],
                'activity_positive_days':active_days,'new_onset_positive_days':onset_days,
                'triggered_day_count':sum(LEVEL_ORDER[r['demo_alert_level']]>=1 for r in rows),
                'alert_message':('Historical simulation: review '+d+' in '+b+'; demo '+level+' priority.') if first is not None else
                    ('Historical simulation: '+d+' in '+b+' has no configured demonstration alert trigger.'),
                'recommended_officer_action':RULES['recommended_officer_action'][level],
                'explanation_type':'RULE_RATIONALE_ONLY_NO_SHAP_NO_GRADCAM',
                'is_live_prediction':False,'simulation_only':True,
            }
            block_disease.append(entry)
    block_summary=[]
    for b in BLOCKS:
        items=[r for r in block_disease if r['block_id']==b]
        overall=max((r['seven_day_overall_demo_level'] for r in items),key=lambda x:LEVEL_ORDER[x])
        block_summary.append({
            'block_id':b,'overall_demo_level':overall,
            'high_disease_count':sum(r['seven_day_overall_demo_level']=='DEMO_HIGH' for r in items),
            'watch_disease_count':sum(r['seven_day_overall_demo_level']=='DEMO_WATCH' for r in items),
            'info_disease_count':sum(r['seven_day_overall_demo_level']=='DEMO_INFO' for r in items),
            'active_demo_alerts':[r for r in items if r['first_alert_day'] is not None],
            'mode':'HISTORICAL_SIMULATION_ONLY',
        })
    counts=Counter(r['demo_alert_level'] for r in daily)
    summary={
        'forecast_origin_date':next(iter(origins)),'daily_rows':len(daily),
        'block_disease_rows':len(block_disease),'blocks':len(BLOCKS),
        'diseases':len(DISEASES),'horizons':len(DAYS),
        'daily_demo_level_counts':{k:counts.get(k,0) for k in LEVEL_ORDER},
        'block_disease_alerts_watch_or_high':sum(r['first_alert_day'] is not None for r in block_disease),
        'blocks_high_overall':sum(r['overall_demo_level']=='DEMO_HIGH' for r in block_summary),
    }
    warnings=[
        'SIMULATION ONLY: forecasts are historical validation-origin 2025-12-24, not current/live.',
        'Alert thresholds are illustrative heuristics, NOT tea-estate validated agronomic thresholds.',
        'Explanations describe transparent alert rules. They are NOT SHAP, Grad-CAM++, causal explanations, or learned feature attributions.',
        'Uncalibrated classifier scores are not calibrated disease probabilities and are NOT used as alert percentages.',
        'Predicted sample-incidence percentage is NOT leaf lesion-area disease severity.',
        'NASA single-point climate is not verified as the Nuwara Eliya estate climate; selected Step38 climate model is a disease-only baseline.',
        'New user observations DO NOT modify these snapshots; dynamic any-block reforecast needs separate FastAPI and feature-state rebuilding.',
        'Consult a qualified tea agronomist; no chemical/pesticide treatment is prescribed by these demo rules.',
    ]
    export={
        'schema_version':'step41-m05-historical-rule-alerts-v1',
        'metadata':{
            'mode':'HISTORICAL_SIMULATION_NOT_LIVE','forecast_origin_date':summary['forecast_origin_date'],
            'is_live_prediction':False,'field_validated':False,
            'alert_thresholds_field_validated':False,
            'explanation_type':'RULE_RATIONALE_ONLY_NOT_MODEL_XAI',
            'model_inference_recomputed_in_step41':False,
            'new_observation_reforecast_supported_here':False,
        },
        'rules':RULES,'summary':summary,
        'daily_triage':daily,'block_disease_alerts':block_disease,
        'block_summaries':block_summary,'warnings':warnings,
    }
    od=root/OUT;od.mkdir(parents=True,exist_ok=True)
    out_json=od/'step41_historical_alerts.json'
    out_json.write_text(json.dumps(export,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
    out_daily=od/'step41_daily_demo_alerts.csv'
    fields=['forecast_origin_date','forecast_target_date','block_id','disease_name','horizon_day',
            'demo_alert_level','trigger_codes','incidence_percent_prediction','activity_predicted_class',
            'new_onset_predicted_class','last_simulated_sample_incidence_pct','explanation_type','simulation_only','is_live_prediction']
    with out_daily.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader()
        for item in daily:
            row=dict(item);row['trigger_codes']='|'.join(row['trigger_codes']);w.writerow(row)
    out_alert=od/'step41_block_disease_alerts.csv'
    cols=['block_id','disease_name','forecast_origin_date','seven_day_overall_demo_level','first_alert_day',
          'peak_predicted_incidence_pct','peak_incidence_day','triggered_day_count','alert_message','simulation_only']
    with out_alert.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore');w.writeheader();w.writerows(block_disease)
    contract_out=od/'step41_frontend_alert_contract.json'
    contract_out.write_text(json.dumps({
        'schema_version':'step41-m05-rule-alert-contract-v1',
        'source':'Step40 historical 448-row simulation export',
        'frontend_badge':'HISTORICAL SIMULATION — NOT LIVE',
        'read_only_service':'src/m05_explainability_alerts/m05_alert_service.py',
        'select_keys':['block_id','disease_name','horizon_day'],
        'levels':['DEMO_INFO','DEMO_WATCH','DEMO_HIGH'],
        'summary_path':str(OUT/'step41_historical_alerts.json'),
        'dynamic_reforecast_implemented':False,
        'xai_supported_in_this_step':'alert rule explanation ONLY; not CNN Grad-CAM++ or model feature SHAP',
        'warnings':warnings
    },indent=2)+'\n',encoding='utf-8')
    report=root/REPORT;report.parent.mkdir(parents=True,exist_ok=True)
    if sha256(source)!=hash_before: fail('source snapshot changed unexpectedly')
    report.write_text(json.dumps({
        'status':'PASS_HISTORICAL_SIMULATION_RULE_EXPLANATION_ONLY',
        'source_sha256_before_after':hash_before,
        'source_unchanged':True,'test_dataset_opened':False,
        'models_trained_or_recalculated':False,
        'summary':summary,'export_json':str(out_json),'warnings':warnings
    },indent=2)+'\n',encoding='utf-8')
    print('='*81)
    print('STEP 41 - m05 DEMO ALERTS + RULE EXPLANATIONS | HISTORICAL SIMULATION')
    print('='*81)
    print(f'Origin={summary["forecast_origin_date"]} | 16 blocks x 4 diseases x 7 days = {len(daily)} rows')
    print(f'Block-disease summaries={len(block_disease)} | Block cards={len(block_summary)}')
    print(f'Daily triage counts: {summary["daily_demo_level_counts"]}')
    print(f'Block-disease alerts: {summary["block_disease_alerts_watch_or_high"]} | Blocks DEMO_HIGH: {summary["blocks_high_overall"]}')
    print(f'JSON: {out_json}\nDaily CSV: {out_daily}\nAlert CSV: {out_alert}\nContract: {contract_out}\nAudit: {report}')
    print('PASS: rule explanations and demo alerts generated; source unchanged.')
    print('WARNING: NO SHAP/Grad-CAM, NO calibrated risk probabilities, NO live updates, NO field-approved thresholds.')
    return export

if __name__=='__main__':
    run()
