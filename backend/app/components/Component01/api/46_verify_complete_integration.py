#!/usr/bin/env python3
"""Step 46 — read-only source + full dynamic FastAPI integration regression.

Usage from E:\\J26-IT-415 with the Component01 .venv activated:
  python backend/app/components/Component01/api/46_verify_complete_integration.py --mode quick
  python backend/app/components/Component01/api/46_verify_complete_integration.py --mode full

The program uses the real in-process FastAPI app and real saved model inference.
All tests of saving observations or latest forecasts use isolated TEMPORARY
storage. Dataset/model files and existing data/runtime/ are not modified.
Image overlay/heatmap PNGs are also redirected to temporary storage.

CONTRACTS mode runs only schema/input/image tests for fixture-based verification.
It does NOT claim to verify trained spread models or historical dashboards.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, timedelta
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from time import perf_counter
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

# Import by normal module import to preserve postponed Pydantic model resolution.
import step43_app
import step45_app
import dynamic_spread_service as dynamic

ROOT = Path(__file__).resolve().parents[1]
BLOCKS = [f'B{i:02d}' for i in range(1, 17)]
DISEASES = list(dynamic.DISEASES)
ORIGIN = '2025-12-24'


def require(ok, note):
    if not ok:
        raise AssertionError(note)


def good(resp, label):
    require(resp.status_code == 200,
            f'{label}: unexpected HTTP {resp.status_code}: {resp.text[:700]}')
    return resp.json()


def sha256_if_exists(path):
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for part in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(part)
    return digest.hexdigest()


def protected_paths(root):
    return [
        root/'data/runtime/officer_observations.csv',
        root/'outputs/dashboard/dynamic/step42_latest_officer_forecast.json',
    ]


def first_training_image():
    manifest = ROOT/'data/processed/image_split_manifest_DEV_ONLY.csv'
    require(manifest.is_file(), f'Missing image manifest: {manifest}')
    with manifest.open(encoding='utf-8-sig', newline='') as file:
        for record in csv.DictReader(file):
            if record.get('split') != 'dev_train':
                continue
            photo = (ROOT/record['relative_path']).resolve()
            require(photo.is_relative_to(ROOT.resolve()), 'Image manifest path escaped project root')
            require(photo.is_file(), f'Image file missing: {photo}')
            return photo
    raise AssertionError('No dev_train image in manifest')


def fixture_and_http_contracts(client, report):
    root = good(client.get('/'), 'root')
    require('SIMULATION' in root.get('mode', ''), 'Root missing simulation label')
    blocks = good(client.get('/api/estate/blocks'), 'blocks')
    require(blocks['count'] == 16 and [r['block_id'] for r in blocks['blocks']] == BLOCKS,
            'Block list contract mismatch')
    diseases = good(client.get('/api/estate/diseases'), 'diseases')
    require(diseases['count'] == 4 and diseases['diseases'] == DISEASES,
            'Disease list contract mismatch')
    good(client.get('/openapi.json'), 'OpenAPI schema')
    status = good(client.get('/api/image/status'), 'image status')
    require(status['checkpoint_present'] and status['image_api_available'],
            f'CNN smoke checkpoint not ready: {status}')
    sample = {'block_id': 'B11', 'disease': 'Red Rust',
              'inspected_bushes': 100, 'symptomatic_bushes': 30}
    observed = good(client.post('/api/severity/incidence', json=sample), 'incidence')
    require(abs(float(observed['incidence_percent'])-30.0) < 1e-8,
            'Incorrect inspected/symptomatic incidence formula')
    require(observed.get('leaf_lesion_area_severity') is None,
            'Incidence must never be labelled as lesion-area severity')
    invalid = [
        {'block_id':'B17','disease':'Red Rust','inspected_bushes':100,'symptomatic_bushes':5},
        {'block_id':'B01','disease':'healthy','inspected_bushes':100,'symptomatic_bushes':5},
        {'block_id':'B01','disease':'Red Rust','inspected_bushes':10,'symptomatic_bushes':20},
        {'block_id':'B01','disease':'Red Rust','inspected_bushes':0,'symptomatic_bushes':0},
        {'block_id':'B01','disease':'Red Rust','inspected_bushes':10.5,'symptomatic_bushes':2},
        {'block_id':'B01','disease':'Red Rust','inspected_bushes':20,'symptomatic_bushes':-1},
    ]
    for idx, payload in enumerate(invalid):
        resp = client.post('/api/forecast/preview', json=payload)
        require(resp.status_code == 422,
                f'Invalid payload #{idx} accepted or unexpected error: HTTP {resp.status_code}')
    report['checks'].append('base API, 16 blocks, 4 diseases, incidence, OpenAPI, invalid inputs PASS')
    print('PASS: Base API, CNN status, incidence, 6 invalid-input checks', flush=True)


def image_api(client, report):
    photo=first_training_image()
    mime={'.jpg':'image/jpeg','.jpeg':'image/jpeg','.png':'image/png','.webp':'image/webp'}.get(photo.suffix.lower())
    require(mime is not None, f'Unsupported fixture: {photo.name}')
    payload=photo.read_bytes()
    with TemporaryDirectory(prefix='step46_image_') as scratch:
        # Image API writes only temporary generated PNGs, not user's previous assets.
        with patch.object(step45_app, 'ASSET_DIR', Path(scratch)):
            r=client.post('/api/image/analyze',files={'file':(photo.name,payload,mime)})
            result=good(r,'actual CNN / Grad-CAM++ image analysis')
            require(result['predicted_class'] in result['class_names'] and len(result['class_names'])==5,
                    'Five-class inference mismatch')
            require(result['full_cnn_training_completed'] is False and
                    result['is_disease_diagnosis_verified'] is False and
                    result['is_leaf_lesion_segmentation'] is False,
                    'Development checkpoint mislabelled as validated')
            for attr in ('heatmap_url','overlay_url'):
                asset_url=result[attr]
                require(asset_url.startswith('/api/image/artifacts/'),f'Bad artifact URL: {attr}')
                asset=client.get(asset_url)
                require(asset.status_code==200 and asset.headers['content-type'].startswith('image/png'),
                        f'PNG GET failed: {attr}: HTTP {asset.status_code}')
                with Image.open(BytesIO(asset.content)) as im:
                    require(im.size==(result['image_width'],result['image_height']),
                            f'Output PNG size mismatch for {attr}')
            for bad_input in (
                {'data':{'target_class':'White Spot'},'files':{'file':(photo.name,payload,mime)}},
                {'files':{'file':('invalid.jpg',b'broken-image','image/jpeg')}},
                {'files':{'file':('invalid.txt',b'not-an-image','text/plain')}},
                {'data':{'target_class':'string'},'files':{'file':(photo.name,payload,mime)}},
            ):
                invalid=client.post('/api/image/analyze',**bad_input)
                require(invalid.status_code in {413,422},
                        f'Unsupported image request accepted: HTTP {invalid.status_code}')
            require(client.get('/api/image/artifacts/not_a_real_png.png').status_code==404,
                    'Missing PNG should return 404')
    report['checks'].append('real 5-class CNN + Grad-CAM++, two PNG GETs, image validation PASS')
    print(f"PASS: CNN + Grad-CAM++ [{result['predicted_class']}], 2 PNG assets, invalid files/targets",flush=True)


def historical_dashboard(client, report):
    meta=good(client.get('/api/metadata'),'metadata')
    require(meta['live_forecast'] is False and meta['forecast_origin_date']==ORIGIN,
            'Forecast incorrectly labelled live or wrong origin')
    health=good(client.get('/health'),'health')
    require(health['status']=='ready',f'Prerequisites incomplete: {health}')
    good(client.get('/api/dashboard/historical/overview'),'dashboard overview')
    good(client.get('/api/alerts/historical/overview'),'alerts overview')
    climate=good(client.get('/api/dashboard/historical/climate?limit=3'),'climate history')
    require(len(climate['monthly_records'])==3,'Historical climate lookup invalid')
    combos=0
    explanations=0
    for block in BLOCKS:
        overview=good(client.get(f'/api/dashboard/historical/blocks/{block}'),f'block dashboard {block}')
        require(len(overview['seven_day_spread_forecasts'])==28 and overview['is_live'] is False,
                f'Historical block overview incomplete: {block}')
        alerts=good(client.get(f'/api/alerts/historical/blocks/{block}'),f'block alerts {block}')
        require(len(alerts['daily_explanations'])==28 and alerts['is_live'] is False,
                f'Historical block alerts incomplete: {block}')
        for disease in DISEASES:
            q={'disease':disease}
            b=good(client.get(f'/api/dashboard/historical/blocks/{block}',params=q),
                   f'historical {block}/{disease}')
            a=good(client.get(f'/api/alerts/historical/blocks/{block}',params=q),
                   f'alert {block}/{disease}')
            assert len(b['block_disease_context'])==1
            require(len(b['seven_day_spread_forecasts'])==7,'Missing 7-day historical forecast')
            require({int(r['horizon_day']) for r in b['seven_day_spread_forecasts']}==set(range(1,8)),
                    'Duplicate/missing historical horizons')
            require(len(a['daily_explanations'])==7 and len(a['block_disease_alerts'])==1,
                    'Missing historical daily alerts')
            # Every day has a front-end accessible rule-based rationale.
            for day in range(1,8):
                d=good(client.get(f'/api/alerts/historical/blocks/{block}/days/{day}',params=q),
                       f'daily rationale {block}/{disease}/{day}')
                require(d['block_id']==block and d['disease_name']==disease and
                        int(d['horizon_day'])==day, 'Wrong rule rationale routing')
                explanations+=1
            combos+=1
    for url in ('/api/dashboard/historical/blocks/B17',
                '/api/alerts/historical/blocks/B17',
                '/api/alerts/historical/blocks/B01/days/8?disease=Red%20Rust'):
        require(client.get(url).status_code==422,f'Invalid historical URL not rejected: {url}')
    report.update({'historical_block_disease_checks':combos,'historical_daily_rule_checks':explanations})
    report['checks'].append('64/64 historical block/disease, 448/448 day explanations PASS')
    print(f'PASS: Historical dashboard/alerts: {combos}/64 combinations, {explanations}/448 daily rationales', flush=True)


def valid_forecast(rec, block, disease):
    require(rec['selected_block_id']==block and rec['disease_name']==disease,
            'Model prediction does not match selected block/disease')
    require(rec.get('actual_saved_model_inference') is True and rec.get('saved') is False,
            'Preview must run models without saving')
    require(rec.get('is_current_live_estate_forecast') is False and
            rec.get('synthetic_estate') is True and
            rec.get('forecast_origin_date')==ORIGIN,
            'Forecast metadata wrongly implies live estate data')
    require(rec.get('feature_columns_count')==48 and rec.get('history_window_days')==14,
            'Saved model input shape contract mismatch')
    seven=rec['selected_block_daily_forecast']
    all_rows=rec['all_block_forecast_for_selected_disease']
    require(len(seven)==7 and len(all_rows)==112,'Expected 7 selected / 112 all-block records')
    require({int(r['horizon_day']) for r in seven}==set(range(1,8)),
            'Selected block has missing/duplicate days')
    require({(r['block_id'],int(r['horizon_day'])) for r in all_rows}==
            {(b,day) for b in BLOCKS for day in range(1,8)},
            'All-block predictions missing/duplicated')
    origin_date=date.fromisoformat(ORIGIN)
    for r in seven:
        day=int(r['horizon_day'])
        require(r['block_id']==block and r['disease_name']==disease and
                r['forecast_target_date']==(origin_date+timedelta(days=day)).isoformat(),
                'Wrong returned block, disease, or target date')
        require(int(r['activity_predicted_class']) in (0,1) and
                int(r['new_onset_predicted_class']) in (0,1) and
                0<=float(r['incidence_percent_prediction'])<=100,
                'Predictions must have valid values')
        for prob in ('activity_probability_uncalibrated','new_onset_probability_uncalibrated'):
            if r[prob] is not None:
                require(0<=float(r[prob])<=1,'Uncalibrated probability out of bounds')
    return seven


def forecast_cases(mode):
    if mode=='quick':
        return [('B01','Brown Blight'),('B06','Red Rust'),
                ('B11','Grey Leaf'),('B16','Red Spider Mite')]
    return [(b,d) for d in DISEASES for b in BLOCKS]


def model_api(client,mode,report):
    # In Step32 SelectedSpreadPredictor is pure inference with checkpoint caches;
    # reuse the SAME actual trained predictor instance to avoid opening 21 saved
    # estimator files again on each of 64 independent in-process API requests.
    import selected_spread_inference as selection
    original=selection.SelectedSpreadPredictor
    instances={}
    def cached_model(root,threads=2):
        key=(str(Path(root).resolve()),threads)
        if key not in instances:
            instances[key]=original(root,threads=threads)
        return instances[key]
    cases=forecast_cases(mode)
    with patch.object(selection,'SelectedSpreadPredictor',cached_model):
        for n,(block,disease) in enumerate(cases,1):
            inspected=100+BLOCKS.index(block)*5
            symptomatic=5+((BLOCKS.index(block)*7+DISEASES.index(disease)*11)%45)
            payload={'block_id':block,'disease':disease,
                     'inspected_bushes':inspected,'symptomatic_bushes':symptomatic}
            rec=good(client.post('/api/forecast/preview',json=payload),
                     f'actual model preview {block}/{disease}')
            valid_forecast(rec,block,disease)
            require(rec['submitted_observation']['inspected_bushes']==inspected and
                    rec['submitted_observation']['symptomatic_bushes']==symptomatic,
                    'Submitted values lost in model output')
            if n%8==0 or n==len(cases):
                print(f'  Real model prediction previews: {n}/{len(cases)} PASS',flush=True)
    report['real_model_block_disease_checks']=len(cases)
    report['checks'].append(f'{len(cases)} actual ML/LSTM API previews PASS; no officer CSV writes')
    return cases


def isolated_save_retrieve(client, report):
    """One real model HTTP save -> CSV read -> latest JSON, redirected to temp files."""
    original_json_writer=dynamic._write_json
    with TemporaryDirectory(prefix='step46_officer_') as workspace:
        sandbox=Path(workspace)
        dest_csv=sandbox/'data/runtime/officer_observations.csv'
        dest_json=sandbox/'outputs/dashboard/dynamic/step42_latest_officer_forecast.json'
        def tmp_runtime(_root=ROOT):
            return dest_csv
        def tmp_json(_path, content):
            return original_json_writer(dest_json, content)
        sample={'block_id':'B12','disease':'Grey Leaf','inspected_bushes':120,'symptomatic_bushes':36}
        # Path patch affects both reading previous updates and storing new ones;
        # Step43 route uses a copied runtime_file reference imported at startup.
        with patch.object(dynamic,'runtime_file',tmp_runtime), \
             patch.object(step43_app,'runtime_file',tmp_runtime), \
             patch.object(dynamic,'_write_json',tmp_json):
            rec=good(client.post('/api/forecast/recalculate',json=sample),
                     'sandboxed actual saved-model recalculate')
            require(rec['saved'] is True and rec['actual_saved_model_inference'] is True,
                    'Save mode did not execute real model or persist')
            require(dest_csv.is_file() and dest_json.is_file(),'Sandbox save missing files')
            records=good(client.get('/api/observations',params={'block_id':'B12'}),
                         'saved sandboxed observations')
            require(records['count']==1 and records['records'][0]['incidence_percent']==30,
                    'Saved record missing/incorrect')
            # Latest GET uses step43_app.ROOT for direct JSON lookup; use a
            # temporary read-only root override on just this GET request.
            with patch.object(step43_app,'ROOT',sandbox):
                latest=good(client.get('/api/forecast/latest',params={'block_id':'B12','disease':'Grey Leaf'}),
                            'saved sandboxed latest forecast')
            require(latest['saved'] is True and latest['selected_block_id']=='B12' and
                    len(latest['selected_block_daily_forecast'])==7,
                    'Latest forecast was not retrieved')
            # A second API preview now reads the newly saved sandbox observation.
            again=good(client.post('/api/forecast/preview',json=sample),
                       'in-memory reforecast using saved sandboxed observation')
            require(again['previous_officer_updates_applied']>=1,
                    'Saved observations not loaded as model input updates')
        report['checks'].append('real-model save -> sandbox CSV -> latest JSON -> re-preview PASS')
        print('PASS: Recalculate/save/retrieve/re-preview using isolated temp files only',flush=True)


def verify(mode, run_image):
    require(ROOT==step45_app.ROOT==step43_app.ROOT, 'Step45 and Step43 do not share same Component01 root')
    protected=protected_paths(ROOT)
    old={str(p):sha256_if_exists(p) for p in protected}
    result={
        'step':46,'mode':mode,'status':'RUNNING','root':str(ROOT),
        'checks':[],'historical_simulation_only':True,'field_validated':False,
        'uses_real_saved_spread_models':mode in {'quick','full'},
        'full_cnn_training_completed':False,
        'no_original_runtime_file_changes':None,
    }
    start=perf_counter()
    try:
        with TestClient(step45_app.app) as client:
            fixture_and_http_contracts(client,result)
            if run_image:
                image_api(client,result)
            if mode in {'quick','full'}:
                historical_dashboard(client,result)
                model_api(client,mode,result)
                isolated_save_retrieve(client,result)
        result['status']='PASS'
    except Exception as error:
        result['status']='FAIL'
        result['error']=f'{type(error).__name__}: {error}'
        print(f'FAIL: {result["error"]}',flush=True)
    finally:
        now={str(p):sha256_if_exists(p) for p in protected}
        result['no_original_runtime_file_changes']=(old==now)
        if old!=now:
            result['status']='FAIL'
            result['error']='PROTECTED original officer observations or latest JSON changed during test'
        result['seconds']=round(perf_counter()-start,2)
        report_dir=ROOT/'outputs/reports/step46_api_regression'
        report_dir.mkdir(parents=True,exist_ok=True)
        dest=report_dir/f'step46_{mode}_audit.json'
        dest.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
        print('='*78)
        print(f"STEP46 {result['mode'].upper()} — {result['status']} | elapsed {result['seconds']}s")
        print(f"Protected officer CSV + last saved forecast unchanged: {result['no_original_runtime_file_changes']}")
        print(f'Report: {dest}')
        print('NOTICE: ALL forecast data are historical synthetic simulation, not live/field validated.')
    return result['status']=='PASS'


def main():
    parser=argparse.ArgumentParser(description='Component01 complete FastAPI regression (Step46)')
    parser.add_argument('--mode',choices=['contracts','quick','full'],default='quick',
                        help='contracts: schema/image only; quick: 4 real forecast combos; full: 64')
    parser.add_argument('--skip-image',action='store_true',help='Skip CNN+Grad-CAM++ API test')
    args=parser.parse_args()
    print('='*78)
    print('STEP46 - RESEARCH PROTOTYPE FASTAPI REGRESSION | HISTORICAL SIMULATION')
    print(f'Mode={args.mode} | CNN image test={not args.skip_image} | Component={ROOT}')
    print('Original officer CSV, latest forecast JSON, models and training CSVs remain unchanged.')
    print('='*78,flush=True)
    sys.exit(0 if verify(args.mode,not args.skip_image) else 1)


if __name__=='__main__':
    main()
