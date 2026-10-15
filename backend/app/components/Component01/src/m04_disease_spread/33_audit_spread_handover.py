"""Step 33: read-only audit of 4-disease Step 32 historical demonstration export.

Checks Step 31-selected model artifacts, Step 26/27 contracts, and Step 32
CSV/JSON/metadata consistency. Does NOT load models, predict, train, touch the
held-out test set, or claim field validation. Safe to run before ZIP handover.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import date, timedelta
import hashlib
import json
import math
from pathlib import Path
import sys

COMPONENT_ROOT = Path(__file__).resolve().parents[2]
DISEASES = {'Brown Blight', 'Grey Leaf', 'Red Rust', 'Red Spider Mite'}
HORIZONS = set(range(1, 8))
FAMILIES = {'ml_winners', 'lstm', 'gcn_lstm'}
TARGET_KINDS = ('Disease_Active', 'Incidence_Pct', 'New_Onset_By')
SCOPE = 'SIMULATION_ONLY_NOT_FIELD_VALIDATED'
RECORD_TYPE = 'HISTORICAL_VALIDATION_DEMONSTRATION_NOT_LIVE'


def ensure(ok, message):
    if not ok:
        raise ValueError(message)


def safe_ref(root, value, why):
    ensure(isinstance(value, str) and bool(value.strip()), f'{why}: missing path')
    p = (root / value).resolve()
    ensure(p.is_relative_to(root), f'{why}: path escapes component root')
    ensure(p.is_file(), f'{why}: file not found: {p}')
    return p


def safe_run_dir(root, value, why):
    ensure(isinstance(value, str) and bool(value.strip()), f'{why}: missing path')
    p = (root / value).resolve()
    ensure(p.is_relative_to(root), f'{why}: path escapes component root')
    ensure(p.is_dir(), f'{why}: model run folder missing: {p}')
    return p


def read_json(path):
    ensure(path.is_file(), f'Missing {path}')
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024), b''):
            h.update(b)
    return h.hexdigest()


def float_num(x, name, *, optional=False):
    if optional and (x is None or x == ''):
        return None
    try:
        v=float(x)
    except (TypeError, ValueError):
        raise ValueError(f'{name}: invalid numeric value {x!r}') from None
    ensure(math.isfinite(v), f'{name}: nonfinite value')
    return v


def integer(x, name):
    v=float_num(x,name)
    ensure(int(v)==v, f'{name}: not an integer')
    return int(v)


def check_bool_false(v, name):
    ensure(v is False or (isinstance(v, str) and v.strip().lower()=='false'), f'{name}: must be false')


def assert_close(x, y, name):
    a=float_num(x,name,optional=True)
    b=float_num(y,name,optional=True)
    ensure(a is None and b is None or a is not None and b is not None and math.isclose(a,b,rel_tol=1e-9,abs_tol=1e-8),
           f'{name}: CSV/JSON mismatch: {a} vs {b}')


def audit(root: Path):
    root=root.resolve()
    spread=root/'outputs/dashboard/spread'
    cp=root/'data/processed'
    checks=[]
    def passed(message): checks.append(message)

    csv_path=spread/'step32_validation_snapshot.csv'
    json_path=spread/'step32_validation_snapshot.json'
    meta_path=spread/'step32_validation_snapshot_metadata.json'
    meta=read_json(meta_path)
    snapshot=read_json(json_path)
    ensure(meta.get('schema_version')=='step32-v1' and meta.get('mode')=='full' and
           meta.get('status')=='PASS_DEMO_EXPORT_NOT_LIVE', 'Step32 full demo export metadata missing or invalid')
    ensure(meta.get('simulation_provenance')==SCOPE, 'Missing explicit simulated provenance')
    for field in ('trained_models_field_validated','test_data_accessed','test_metrics_computed'):
        check_bool_false(meta.get(field),f'Step32 metadata {field}')
    ensure(set(meta.get('disease_names',[]))==DISEASES and len(meta['disease_names'])==4,
           'Expected four distinct disease names')
    block_ids=meta.get('block_ids',[])
    ensure(len(block_ids)==16 and len(set(block_ids))==16, 'Expected 16 unique block IDs')
    ensure(set(meta.get('horizon_days',[]))==HORIZONS, 'Expected 7 horizon days')
    origin=date.fromisoformat(meta['forecast_origin_date'])
    ensure(meta.get('total_records')==448, 'Expected 448 Step32 full snapshot records')
    passed('Step32 metadata: full, historical, simulated, non-live, non-test')

    ensure(snapshot.get('snapshot_type')=='historical_validation_demonstration', 'Bad JSON snapshot type')
    ensure(snapshot.get('forecast_origin_date')==origin.isoformat(), 'CSV/JSON origin mismatch')
    with csv_path.open('r',newline='',encoding='utf-8-sig') as f:
        reader=csv.DictReader(f)
        expected_fields={'disease_name','block_id','horizon_day','activity_predicted_class',
                         'incidence_percent_prediction','new_onset_predicted_class','forecast_origin_date',
                         'forecast_target_date','activity_family','incidence_family','onset_family',
                         'activity_probability_uncalibrated','new_onset_probability_uncalibrated',
                         'data_provenance','record_type','live_estate_forecast'}
        ensure(expected_fields.issubset(set(reader.fieldnames or [])), 'Missing Step32 CSV columns')
        records=list(reader)
    json_records=snapshot.get('records')
    ensure(isinstance(json_records,list) and len(json_records)==448 and len(records)==448,
           'CSV / JSON must each have 448 rows')
    by_key={}
    family_per_target={}
    disease_counts=Counter()
    for row in records:
        disease=row['disease_name'];block=row['block_id']; day=integer(row['horizon_day'],'horizon_day')
        ensure(disease in DISEASES and block in block_ids and day in HORIZONS, 'Unknown disease/block/horizon')
        key=(disease,block,day)
        ensure(key not in by_key, f'Duplicate disease/block/day: {key}')
        by_key[key]=row
        disease_counts[disease]+=1
        ensure(row['forecast_origin_date']==origin.isoformat(), f'Origin mismatch {key}')
        ensure(date.fromisoformat(row['forecast_target_date'])==origin+timedelta(days=day),f'Target date mismatch {key}')
        ensure(row['record_type']==RECORD_TYPE, f'Wrong record type {key}')
        ensure(row['data_provenance']==SCOPE, f'Missing simulation provenance {key}')
        check_bool_false(row['live_estate_forecast'],f'live_estate_forecast for {key}')
        for field in ('activity_predicted_class','new_onset_predicted_class'):
            ensure(integer(row[field],f'{field} {key}') in (0,1), f'Nonbinary class {key}')
        incidence=float_num(row['incidence_percent_prediction'],f'incidence {key}')
        ensure(0<=incidence<=100,f'Incidence percentage out of range {key}')
        for field in ('activity_probability_uncalibrated','new_onset_probability_uncalibrated'):
            value=float_num(row[field],f'{field} {key}',optional=True)
            ensure(value is None or 0<=value<=1,f'Probability out of range {field} {key}')
        for kind,column in (('Disease_Active','activity_family'),('Incidence_Pct','incidence_family'),('New_Onset_By','onset_family')):
            family=row[column]
            ensure(family in FAMILIES, f'Unknown model family {family} for {key}')
            target=f'Target_{kind}_Day_{day}'
            ensure(target not in family_per_target or family_per_target[target]==family,
                   f'Family differs by disease/block for target {target}')
            family_per_target[target]=family
    ensure(all(disease_counts[d]==112 for d in DISEASES), 'Each disease must have 112 block/day rows')
    ensure(len(by_key)==448 and len(family_per_target)==21, 'Expected complete block/disease/horizon grid')
    json_by_key={}
    for row in json_records:
        key=(row['disease_name'],row['block_id'],integer(row['horizon_day'],'JSON horizon'))
        ensure(key not in json_by_key,f'Duplicate JSON key {key}')
        json_by_key[key]=row
    ensure(set(json_by_key)==set(by_key), 'CSV/JSON keys differ')
    for key,row in by_key.items():
        j=json_by_key[key]
        for field in ('disease_name','block_id','forecast_origin_date','forecast_target_date',
                      'record_type','data_provenance','activity_family','incidence_family',
                      'onset_family','activity_model','incidence_model','onset_model'):
            ensure(row.get(field)==j.get(field),f'CSV/JSON {field} differs at {key}')
        for field in ('activity_predicted_class','new_onset_predicted_class'):
            ensure(integer(row[field],f'CSV {field}')==integer(j[field],f'JSON {field}'),f'CSV/JSON {field} mismatch at {key}')
        for field in ('incidence_percent_prediction','activity_probability_uncalibrated','new_onset_probability_uncalibrated'):
            assert_close(row[field],j[field],f'{field} {key}')
        check_bool_false(j.get('live_estate_forecast'),f'JSON live flag {key}')
    passed('448 unique predictions: CSV/JSON match, dates, ranges, provenance, full 4x16x7 grid')

    selection_path=safe_ref(root,meta['selection_file'],'Step31 selection')
    sel=read_json(selection_path)
    ensure(sel.get('mode')=='full' and sel.get('status')=='PASS_VALIDATION_ALIGNED_COMPARISON',
           'Step31 must be the full aligned validation selection')
    check_bool_false(sel.get('test_dataset_accessed'),'Step31 test access')
    chosen=sel.get('selected_families')
    ensure(isinstance(chosen,list) and len(chosen)==21, 'Expected 21 Step31 selected families')
    chosen_map={}
    for obj in chosen:
        target=obj['target']
        ensure(target not in chosen_map and obj.get('selected_family') in FAMILIES,'Duplicate/unknown selection')
        chosen_map[target]=obj['selected_family']
    ensure(chosen_map==family_per_target, 'Step32 actual routing disagrees with Step31 21 selected families')
    counts=dict(Counter(chosen_map.values()))
    ensure(meta.get('model_family_target_counts')==counts, 'Metadata family counts mismatch')
    passed(f'Step31 selection matches all 21 actual model routes: {counts}')

    registry_path=root/'models/spread/multidisease_step32/selected_model_registry.json'
    reg=read_json(registry_path)
    ensure(reg.get('schema_version')=='step32-registry-v1' and reg.get('scope')==SCOPE,
           'Invalid Step32 registry')
    ensure(safe_ref(root,reg['selection'],'Registry selection')==selection_path,
           'Registry points to different selection')
    ensure(reg.get('model_family_target_counts')==counts, 'Registry counts disagree with selected families')
    ensure(reg.get('disease_names')==meta.get('disease_names') and reg.get('block_ids')==block_ids,
           'Registry disease/block order mismatch')
    ensure(reg.get('require_preprocessed_history') is True and
           reg.get('live_observation_feature_pipeline_included') is False,
           'Registry must explicitly state live feature pipeline is NOT implemented')
    features=reg['features']
    ensure(isinstance(features,list) and len(features)==48 and len(set(features))==48 and
           not any(str(f).startswith('Target_') for f in features),
           'Registry feature list invalid/contains future target leakage')
    ft=read_json(cp/'multidisease_feature_contract.json')
    sq=read_json(cp/'multidisease_sequence_graph_contract.json')
    ensure(ft.get('feature_columns')==features and sq.get('input_feature_columns')==features,
           'Step26/27 feature order does not match model registry')
    ensure(sq.get('disease_names')==meta['disease_names'] and sq.get('block_ids')==block_ids and
           sq.get('sequence_days')==14, 'Step27 graph contract mismatch')
    ensure(reg.get('lookback_days')==14 and reg.get('horizon_days')==7,
           'Registry time contract mismatch')
    for path in ('multidisease_step26_feature_pipeline.joblib',
                 'multidisease_sequence_graph_validation.npz',
                 'multidisease_graph_adjacency.npz'):
        ensure((cp/path).is_file(),f'Missing required data-processing artifact: {path}')
    passed('Feature, sequence, graph, registry contracts match (48 features, 14-day lookback, 16 blocks)')

    model_run_paths={}
    model_artifacts=[]
    ensure(set(reg.get('model_runs',{}))==FAMILIES,'Registry does not list all three model runs')
    ensure(set(sel.get('family_runs',{}))==FAMILIES,'Step31 does not list all three model runs')
    for family in sorted(FAMILIES):
        run=safe_run_dir(root,reg['model_runs'][family],f'{family} model run')
        ensure(run==safe_run_dir(root,sel['family_runs'][family],f'{family} selected run'),
               f'{family} registry points to different training run')
        m=read_json(run/'manifest.json')
        if family=='ml_winners':
            ensure(m.get('mode')=='full' and m.get('model_count')==21 and
                   m.get('feature_columns')==features and m.get('disease_names')==meta['disease_names'],
                   'ML trained model manifest incompatible')
            winners=m.get('chosen')
            ensure(isinstance(winners,list) and len(winners)==21, 'ML 21 checkpoints manifest missing')
            for winner in winners:
                check_path=(run/winner['checkpoint']).resolve()
                ensure(check_path.is_relative_to(run) and check_path.is_file() and check_path.stat().st_size>0,
                       f'ML checkpoint missing/corrupted for {winner.get("target")}')
                model_artifacts.append(check_path)
        else:
            expected_file='best_lstm_weights.pt' if family=='lstm' else 'best_gcn_lstm_weights.pt'
            ckpt=m.get('checkpoint')
            ensure(ckpt is not None,f'{family} checkpoint field missing')
            # Most script versions store basename. Accept path relative to component or model run.
            candidate=(run/ckpt).resolve()
            if not candidate.is_file():
                candidate=(root/ckpt).resolve()
            ensure(candidate.is_relative_to(root) and candidate.is_file() and candidate.stat().st_size>0 and
                   candidate.name==expected_file, f'{family} checkpoint missing or unexpected')
            model_artifacts.append(candidate)
        model_run_paths[family]=str(run.relative_to(root))
    passed('21 ML model checkpoints + LSTM + GCN-LSTM artifacts exist (read-only audit)')

    manifest_files=[csv_path,json_path,meta_path,selection_path,registry_path,
                    cp/'multidisease_feature_contract.json',
                    cp/'multidisease_sequence_graph_contract.json',
                    cp/'multidisease_step26_feature_pipeline.joblib',
                    cp/'multidisease_sequence_graph_validation.npz',
                    cp/'multidisease_graph_adjacency.npz'] + model_artifacts
    file_integrity=[{'relative_path':str(p.relative_to(root)).replace('\\','/'),
                     'bytes':p.stat().st_size,'sha256':digest(p)} for p in manifest_files]
    report={
        'step':33,
        'status':'PASS_HISTORICAL_SIMULATION_DEMO_HANDOVER_AUDIT',
        'scientific_status':'NOT_FIELD_VALIDATED',
        'dynamic_live_api_ready':False,
        'note':'This audits stored files and contracts, not predictive correctness or new officer-observation inference.',
        'snapshot_origin':origin.isoformat(),
        'records':len(records),'disease_count':4,'block_count':16,'forecast_days':7,
        'feature_count':48,'lookback_days':14,'model_family_target_counts':counts,
        'selected_model_runs':model_run_paths,
        'test_data_used_in_step33':False,
        'checks_passed':checks,
        'files_checked_with_sha256':file_integrity,
        'limitations':[
            'All four spread disease datasets and estate blocks are synthetic or dummy; no field validation.',
            'Climate source coordinates must be checked against the intended estate.',
            'Snapshot origin is historical validation date, not current/date-selectable live forecast.',
            'Saved models cannot consume raw new officer observations directly; live feature assembly, history updates and persistence are NOT implemented.',
            'Validation data reused for model family selection; selected scores may be optimistic.',
            'No scientifically validated risk thresholds or calibrated disease probabilities.',
            'Final ZIP still requires m01/m02/m03/m05, API, dashboard handover and fresh-install tests.',
        ],
    }
    reports=root/'outputs/reports/multidisease_step33'
    reports.mkdir(parents=True,exist_ok=True)
    report_path=reports/'step33_m04_handover_audit.json'
    report_path.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    summary_path=reports/'step33_m04_handover_summary.md'
    summary_path.write_text(
        '# Step 33 — m04 Handover Audit\n\n'
        '**Status:** PASS — stored historical simulation demo only.\n\n'
        f'- Diseases: 4; blocks: 16; forecast days: 7; rows: {len(records)}\n'
        f'- Historical validation origin: {origin.isoformat()}\n'
        f'- Selected target families: {json.dumps(counts,sort_keys=True)}\n'
        '- Data: **SIMULATED**, estate grid: **DUMMY**, source climate site: **NOT VERIFIED**.\n'
        '- No test split accessed by this audit. No training, test scoring or new predictions.\n'
        '- Not live-ready: additional observation ingestion, feature/historical-window recomputation, database and FastAPI required.\n'
        '- Not final research validation or a current estate forecast.\n\n'
        '## Audit checks\n'+''.join(f'- {v}\n' for v in checks)+'\n'
        'See `step33_m04_handover_audit.json` for SHA-256 file list and limitations.\n',
        encoding='utf-8')
    print('='*75)
    print('STEP 33 - m04 HISTORICAL SIMULATION HANDOVER AUDIT')
    print('='*75)
    print(f'Origin={origin.isoformat()} | records=448 | diseases=4 | blocks=16 | days=7')
    print(f'Families (21 targets): {counts}')
    for item in checks: print('  PASS:',item)
    print('Status: PASS_HISTORICAL_SIMULATION_DEMO_HANDOVER_AUDIT')
    print('Report:',report_path)
    print('Summary:',summary_path)
    print('CAUTION: NOT field validated; NOT a live update/API feature; next modules remain.')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--component-root',type=Path,default=COMPONENT_ROOT,
                        help='Optional alternative Component01 folder, for audit tests')
    args=parser.parse_args()
    try:
        audit(args.component_root)
    except (ValueError,KeyError,TypeError,IndexError,json.JSONDecodeError,OSError) as exc:
        print('FAIL — Step33 audit:',exc,file=sys.stderr)
        return 1
    return 0


if __name__=='__main__':
    raise SystemExit(main())
