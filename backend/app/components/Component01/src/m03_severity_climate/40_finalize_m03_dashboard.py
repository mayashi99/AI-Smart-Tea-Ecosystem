#!/usr/bin/env python3
"""Step40: audited HISTORICAL simulation dashboard combining m03 and m04 exports.

No future/test rows, no model training, no live forecasting and no invented
lesion measurements. Weather history is cut off strictly BEFORE origin-month.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from datetime import timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DISEASES = {'Brown Blight', 'Grey Leaf', 'Red Rust', 'Red Spider Mite'}
BLOCKS = {f'B{i:02d}' for i in range(1, 17)}
SOURCES = {
    'incidence': 'outputs/dashboard/severity/step39_incidence_dashboard.csv',
    'incidence_meta': 'outputs/dashboard/severity/step39_metadata.json',
    'step35': 'outputs/dashboard/climate/step35_block_incidence_snapshot.csv',
    'step35_meta': 'outputs/dashboard/climate/step35_historical_context_summary.json',
    'climate_scores': 'outputs/dashboard/climate/step38_climate_risk_validation_snapshot.csv',
    'climate_registry': 'models/climate/step38/climate_risk_registry.json',
    'spread': 'outputs/dashboard/spread/step32_validation_snapshot.csv',
    'spread_meta': 'outputs/dashboard/spread/step32_validation_snapshot_metadata.json',
    'monthly': 'outputs/dashboard/climate/climate_monthly_summary.csv',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def serial_records(df):
    """Pandas handles NaN -> JSON null and numpy scalar normalization."""
    return json.loads(df.to_json(orient='records', date_format='iso', double_precision=10))


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        while part := f.read(1024 * 1024):
            h.update(part)
    return h.hexdigest()


def check_required(df, cols, label):
    missing = set(cols) - set(df.columns)
    require(not missing, f'{label}: missing required columns: {sorted(missing)}')


def prepare(root):
    root = root.resolve()
    paths = {k: root / v for k, v in SOURCES.items()}
    for k, path in paths.items():
        require(path.is_file(), f'Missing prerequisite {k}: {path}. Run Steps 32, 34, 35, 38, 39 first.')
    input_hashes_before = {k: sha256(p) for k,p in paths.items()}
    inspection = pd.read_csv(paths['incidence'])
    step35 = pd.read_csv(paths['step35'])
    scores = pd.read_csv(paths['climate_scores'])
    spread = pd.read_csv(paths['spread'])
    monthly = pd.read_csv(paths['monthly'])
    imeta = read_json(paths['incidence_meta'])
    smeta = read_json(paths['step35_meta'])
    rmeta = read_json(paths['climate_registry'])
    fmeta = read_json(paths['spread_meta'])

    require(imeta.get('step') == 39 and imeta.get('synthetic_inspections_only') is True
            and imeta.get('leaf_lesion_area_measurements_in_historical_export') == 0
            and imeta.get('locked_test_used') is False, 'Step39 simulation-only provenance invalid.')
    require(smeta.get('step') == 35 and smeta.get('status') == 'PASS_HISTORICAL_SIMULATION_CONTEXT_ONLY'
            and smeta.get('test_rows_used') is False and smeta.get('future_targets_used') is False
            and smeta.get('observations_at_or_before_origin_only') is True,
            'Step35 origin/leakage/provenance contract invalid.')
    require(fmeta.get('schema_version') == 'step32-v1' and fmeta.get('mode') == 'full'
            and fmeta.get('total_records') == 448 and fmeta.get('test_data_accessed') is False
            and fmeta.get('status') == 'PASS_DEMO_EXPORT_NOT_LIVE', 'Step32 must be full historical-validation export.')
    require(rmeta.get('schema') == 'step38-climate-risk-v1' and rmeta.get('split', {}).get('locked_test_evaluated') is False
            and rmeta.get('nasa_estate_location_verified') is False,
            'Step38 climate registry provenance invalid.')

    origin = str(smeta['forecast_origin_date'])
    require(origin == str(imeta['historical_origin']) == str(fmeta['forecast_origin_date']) == str(rmeta['snapshot_origin']),
            'Source origin mismatch: climate/incidence/spread must be same validation origin.')
    origin_ts = pd.Timestamp(origin)
    require(origin_ts.year == 2025, 'This export is reserved for 2025 historical validation; not current/live.')
    check_required(inspection, ['forecast_origin_date','disease_name','block_id','block_name',
        'last_inspection_date','inspected_bushes','symptomatic_bushes','sample_incidence_pct',
        'is_simulated','is_field_validated','is_lesion_area_severity','leaf_lesion_area_pct',
        'leaf_area_severity_status'], 'Step39')
    check_required(step35, ['forecast_origin_date','disease_name','block_id','sample_incidence_pct'], 'Step35')
    check_required(scores, ['Forecast_Origin_Date','Forecast_Target_Date','Disease_Name',
        'Day7_Activity_Score','Day7_New_Onset_Score','Activity_Model','New_Onset_Model',
        'Shared_Across_All_16_Simulated_Blocks','Climate_Point_Verified_For_Target_Estate','Synthetic_Model'], 'Step38')
    check_required(spread, ['forecast_origin_date','forecast_target_date','disease_name','block_id','horizon_day',
        'incidence_percent_prediction','activity_probability_uncalibrated','new_onset_probability_uncalibrated',
        'record_type','live_estate_forecast'], 'Step32')
    check_required(monthly, ['Year_Month','Month_Complete','Rainfall_Total_Mm',
                             'Temperature_Mean_C','Humidity_Mean_Pct'], 'Step34 monthly')

    keys = ['forecast_origin_date','disease_name','block_id']
    require(len(inspection) == len(step35) == 64 and not inspection.duplicated(keys).any()
            and not step35.duplicated(keys).any(), 'Expected 64 unique source incidence records.')
    for name, df in [('Step35',step35),('Step39',inspection)]:
        require(set(df['disease_name']) == DISEASES and set(df['block_id']) == BLOCKS
                and df['forecast_origin_date'].eq(origin).all(), f'{name} coverage or origin mismatch.')
    require(inspection['is_simulated'].eq(True).all() and inspection['is_field_validated'].eq(False).all()
            and inspection['is_lesion_area_severity'].eq(False).all()
            and inspection['leaf_lesion_area_pct'].isna().all(),
            'Cannot publish field-validated or fabricated leaf-area severity.')
    require((pd.to_datetime(inspection['last_inspection_date']) <= origin_ts).all(),
            'Future inspection date found: leakage.')
    cnt_in = pd.to_numeric(inspection['inspected_bushes'],errors='raise')
    cnt_sym = pd.to_numeric(inspection['symptomatic_bushes'],errors='raise')
    actual_pct = cnt_sym / cnt_in * 100
    require(((cnt_in > 0) & (cnt_sym >= 0) & (cnt_sym <= cnt_in)).all()
            and ((actual_pct - inspection['sample_incidence_pct']).abs() <= .000051).all(),
            'Invalid inspection counts or percentage mismatch.')
    matched = inspection.merge(step35[keys + ['sample_incidence_pct']], on=keys,
                               validate='one_to_one', suffixes=('', '_step35'), indicator=True)
    require(len(matched)==64 and matched['_merge'].eq('both').all()
            and (matched['sample_incidence_pct'] - matched['sample_incidence_pct_step35']).abs().lt(.00001).all(),
            'Step39 incidence records do not match Step35.')

    require(len(scores) == 4 and not scores.duplicated(['Disease_Name','Forecast_Origin_Date']).any()
            and set(scores['Disease_Name']) == DISEASES and scores['Forecast_Origin_Date'].eq(origin).all(),
            'Expected exactly one climate score for each disease at origin.')
    require(scores['Forecast_Target_Date'].eq(str((origin_ts+pd.Timedelta(days=7)).date())).all(),
            'Step38 expected Day7 climate background horizon.')
    require(scores['Shared_Across_All_16_Simulated_Blocks'].eq(True).all()
            and scores['Climate_Point_Verified_For_Target_Estate'].eq(False).all()
            and scores['Synthetic_Model'].eq(True).all(),
            'Refusing to publish block-specific or estate-verified climate claims.')
    require((scores[['Day7_Activity_Score','Day7_New_Onset_Score']] >= 0).all().all()
            and (scores[['Day7_Activity_Score','Day7_New_Onset_Score']] <= 1).all().all(),
            'Climate background score outside [0,1].')
    climate = scores.rename(columns={
        'Forecast_Origin_Date':'forecast_origin_date','Disease_Name':'disease_name',
        'Day7_Activity_Score':'climate_background_day7_activity_score',
        'Day7_New_Onset_Score':'climate_background_day7_new_onset_score',
        'Activity_Model':'climate_background_activity_model',
        'New_Onset_Model':'climate_background_onset_model',
        'Activity_Descriptive_Band':'climate_activity_descriptive_band',
        'New_Onset_Descriptive_Band':'climate_onset_descriptive_band',
    })
    climate_cols = ['forecast_origin_date','disease_name',
        'climate_background_day7_activity_score','climate_background_day7_new_onset_score',
        'climate_background_activity_model','climate_background_onset_model',
        'climate_activity_descriptive_band','climate_onset_descriptive_band']
    context = inspection.merge(climate[climate_cols], on=['forecast_origin_date','disease_name'],
                               how='left', validate='many_to_one', indicator=True)
    require(len(context)==64 and context['_merge'].eq('both').all(), 'Climate-incidence cross join failed.')
    context.drop(columns='_merge',inplace=True)
    weather = smeta['historical_climate_last_seven_days']
    require(weather.get('point_location_verified_to_estate') is False
            and weather.get('end_date') == origin, 'Step35 historical climate date/provenance mismatch.')
    context['historical_7d_temp_mean_c'] = weather['mean_temperature_c']
    context['historical_7d_humidity_mean_pct'] = weather['mean_relative_humidity_pct']
    context['historical_7d_rainfall_total_mm'] = weather['total_rainfall_mm']
    context['historical_7d_solar_mean'] = weather['mean_solar_allsky']
    context['simulation_only'] = True
    context['climate_background_is_block_specific'] = False
    context['is_live_prediction'] = False
    context = context.sort_values(['block_id','disease_name']).reset_index(drop=True)

    # Only complete months STRICTLY BEFORE forecast origin month. Source Dec-2025
    # summary contains dates after origin 2025-12-24 and must not enter dashboard.
    require(monthly['Year_Month'].astype(str).str.fullmatch(r'\d{4}-\d{2}').all(), 'Invalid monthly year-month')
    month = origin[:7]
    eligible = monthly.loc[monthly['Year_Month'].lt(month) & monthly['Month_Complete'].eq(1)].copy()
    require(len(eligible)>=12 and eligible[['Temperature_Mean_C','Humidity_Mean_Pct','Rainfall_Total_Mm']].notna().all().all(),
            'Not enough complete historical monthly climate records.')
    eligible.sort_values('Year_Month',inplace=True)
    require(eligible['Year_Month'].max() < month, 'Future origin-month climate could leak.')

    require(len(spread)==448 and not spread.duplicated(keys+['horizon_day']).any()
            and set(spread['disease_name'])==DISEASES and set(spread['block_id'])==BLOCKS
            and spread['forecast_origin_date'].eq(origin).all(), 'Step32 spread origin/coverage mismatch.')
    spread['horizon_day'] = pd.to_numeric(spread['horizon_day'],errors='raise').astype(int)
    require(set(spread['horizon_day']) == set(range(1,8))
            and spread.groupby(['disease_name','block_id'])['horizon_day'].nunique().eq(7).all(),
            'Missing horizon forecast for some block/disease.')
    require(spread['live_estate_forecast'].eq(False).all()
            and spread['record_type'].eq('HISTORICAL_VALIDATION_DEMONSTRATION_NOT_LIVE').all(),
            'No live/real-time forecasts may be published by Step40.')
    dates = pd.to_datetime(spread['forecast_target_date'],errors='raise')
    require(((dates-origin_ts).dt.days == spread['horizon_day']).all(),
            'Forecast target and horizon mismatch.')
    integrated = spread.merge(context, on=keys, how='left', validate='many_to_one', indicator=True)
    require(len(integrated)==448 and integrated['_merge'].eq('both').all(),
            '7-day spread to m03 climate/incidence join failed.')
    integrated.drop(columns='_merge', inplace=True)
    integrated.sort_values(['block_id','disease_name','horizon_day'],inplace=True)

    dest = root/'outputs/dashboard/m03'
    dest.mkdir(parents=True, exist_ok=True)
    context_csv = dest/'step40_historical_block_context.csv'
    integrated_csv = dest/'step40_historical_seven_day_integrated.csv'
    dashboard_json = dest/'step40_historical_dashboard.json'
    contract_json = dest/'step40_dashboard_contract.json'
    audit_file = root/'outputs/reports/step40_m03_final_audit.json'

    historical_meta = {
        'mode':'HISTORICAL_VALIDATION_SIMULATION_NOT_LIVE',
        'forecast_origin_date':origin,
        'forecast_available_horizon_days':list(range(1,8)),
        'diseases':sorted(DISEASES), 'blocks':sorted(BLOCKS),
        'nasa_climate_latitude':rmeta['nasa_point']['latitude'],
        'nasa_climate_longitude':rmeta['nasa_point']['longitude'],
        'target_estate_location_verified':False,
        'climate_model_selected_activity':rmeta['selected']['Target_Disease_Active_Day_7']['name'],
        'climate_model_selected_onset':rmeta['selected']['Target_New_Onset_By_Day_7']['name'],
        'block_specific_climate_inference':False,
        'field_validated':False,
        'leaf_area_severity_validated':False,
        'dynamic_observation_reforecast_available':False,
        'locked_test_evaluated':False,
        'safe_climate_monthly_cutoff_exclusive':month,
        'historical_climate_last_7d':weather,
    }
    payload = {
        'schema_version':'step40-m03-dashboard-v1',
        'metadata':historical_meta,
        'summary':{
            'block_disease_rows':64,
            'seven_day_spread_rows':448,
            'complete_historical_months':len(eligible),
            'earliest_historical_climate_month':str(eligible['Year_Month'].min()),
            'latest_historical_climate_month':str(eligible['Year_Month'].max()),
        },
        'block_disease_context':serial_records(context),
        'seven_day_spread_forecasts':serial_records(integrated),
        'climate_monthly_history':serial_records(eligible),
        'warnings':[
            'SIMULATION ONLY: disease labels and estate blocks are synthetic.',
            'ALL predictions are from historical validation origin; not current date or live.',
            'Climate source (6.7789,79.9301) is not verified for Nuwara Eliya estate.',
            'Step38 validation selected disease-only baseline, not an established weather effect.',
            'Sample incidence of symptomatic bushes is NOT leaf lesion-area severity.',
            'Image-based color segmentation is an unvalidated demonstration, not clinical/agronomic severity.',
            'Step32 class probabilities are not calibrated; do not treat as verified probabilities.',
            'New officer input requires separate dynamic feature reconstruction/reforecast API.',
            'No locked test data was loaded to construct Step40 outputs.',
        ],
    }
    contract = {
        'schema_version':'step40-m03-dashboard-contract-v1',
        'frontend_mode':'HISTORICAL_SIMULATION_DEMO_ONLY',
        'csv_context_file':str(context_csv.relative_to(root)).replace('\\','/'),
        'csv_seven_day_file':str(integrated_csv.relative_to(root)).replace('\\','/'),
        'json_dashboard_file':str(dashboard_json.relative_to(root)).replace('\\','/'),
        'api_ready_functions':{
            'get_overview':'m03_dashboard_service.get_overview(root)',
            'get_block_dashboard':'m03_dashboard_service.get_block_dashboard(root, block_id, disease=None)',
            'get_climate_history':'m03_dashboard_service.get_climate_history(root,limit=12)',
        },
        'primary_selection_keys':['block_id','disease_name','horizon_day'],
        'example_block_id':'B16',
        'example_disease':'Red Rust',
        'known_blocks':sorted(BLOCKS),
        'known_diseases':sorted(DISEASES),
        'severity_ui':{
            'supported':'sample_incidence_pct from officer sample counts',
            'leaf_lesion_area_pct':'null in historical export; image mask demo separate',
        },
        'no_database_needed':True,
        'dynamic_predictions_implemented_here':False,
        'simulation_badge_required':True,
        'warning':'Historical demo export; not a live, dynamically recalculated forecast.',
    }
    context.to_csv(context_csv,index=False,na_rep='')
    integrated.to_csv(integrated_csv,index=False,na_rep='')
    write_json(dashboard_json,payload)
    write_json(contract_json,contract)

    input_hashes_after = {k: sha256(p) for k,p in paths.items()}
    require(input_hashes_after == input_hashes_before, 'Prerequisite input files changed unexpectedly.')
    audit = {
        'step':40,
        'status':'PASS_M03_HISTORICAL_SIMULATION_DASHBOARD_HANDOVER_READY',
        'historical_origin':origin,
        'block_disease_context_rows':len(context),
        'seven_day_spread_rows':len(integrated),
        'historical_complete_month_rows':len(eligible),
        'climate_month_last_included':str(eligible['Year_Month'].max()),
        'origin_month_intentionally_excluded':month,
        'split':'historical 2025 validation only, locked test not loaded',
        'all_source_hashes_unchanged':True,
        'source_hashes_sha256':input_hashes_after,
        'climate_risk_climate_effect_proven':False,
        'leaf_lesion_area_validated':False,
        'current_live_forecast':False,
        'dynamic_officer_input_inference_included':False,
        'outputs':[str(p.relative_to(root)).replace('\\','/') for p in (context_csv,integrated_csv,dashboard_json,contract_json)],
        'warnings':payload['warnings'],
    }
    write_json(audit_file, audit)
    print('='*84)
    print('STEP 40 - m03 + m04 HISTORICAL DASHBOARD INTEGRATION | SIMULATION ONLY')
    print('='*84)
    print(f'Origin={origin} | blocks=16 | diseases=4 | context={len(context)} | 7-day rows={len(integrated)}')
    print(f'Historical completed climate months={len(eligible)} | last={eligible.Year_Month.max()} (origin month excluded)')
    print('Climate model selected:',historical_meta['climate_model_selected_activity'], '/',historical_meta['climate_model_selected_onset'])
    print('Context CSV:',context_csv)
    print('Seven-day CSV:',integrated_csv)
    print('Dashboard JSON:',dashboard_json)
    print('Frontend contract:',contract_json)
    print('Final m03 audit:',audit_file)
    print('PASS: All 16 blocks x 4 diseases x 7 horizons joined; historical sources unchanged.')
    print('WARNING: NO live update, NO validated leaf lesion-area measurement or estate climate match.')
    return audit


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--component-root',type=Path,default=ROOT)
    args = ap.parse_args()
    prepare(args.component_root)


if __name__=='__main__':
    main()
