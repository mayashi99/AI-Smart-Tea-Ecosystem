#!/usr/bin/env python3
"""Step 35: historical dashboard climate/inspection-incidence context (SIMULATION ONLY).

Reads Step 32's *historical validation* forecast origin, Step 34's *single-point*
NASA climate-context data, and the Step 23 *simulated* inspection counts.
Never uses future targets, trains a model, or estimates leaf lesion surface area.
"""
from __future__ import annotations

import argparse
import json
from datetime import timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DISEASES = ('Brown Blight', 'Grey Leaf', 'Red Rust', 'Red Spider Mite')
WEATHER = ('T2M', 'RH2M', 'PRECTOTCORR', 'ALLSKY_SFC_SW_DWN')


def check(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def save_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False, default=str), encoding='utf-8')


def incidence_band(pct: float) -> str:
    # Descriptive visualization bands only. NOT agronomic severity cut-offs.
    if pct == 0:
        return 'ZERO_SYMPTOMATIC_BUSHES_IN_SAMPLE'
    if pct <= 10:
        return 'OVER_0_TO_10_PCT'
    if pct <= 25:
        return 'OVER_10_TO_25_PCT'
    return 'OVER_25_PCT'


def run(root: Path) -> dict:
    root = root.resolve()
    base = root / 'outputs/dashboard'
    step32 = base / 'spread/step32_validation_snapshot_metadata.json'
    step34 = base / 'climate/climate_and_incidence_metadata.json'
    weather_path = root / 'data/processed/climate_daily_context.csv'
    data_path = root / 'data/synthetic/synthetic_block_records_multidisease.csv'
    blocks_path = root / 'data/synthetic/estate_blocks.csv'
    for p in (step32, step34, weather_path, data_path, blocks_path):
        if not p.is_file():
            raise FileNotFoundError(f'Prerequisite missing: {p}')

    snap = json.loads(step32.read_text(encoding='utf-8'))
    context = json.loads(step34.read_text(encoding='utf-8'))
    check(snap.get('mode') == 'full' and snap.get('status') == 'PASS_DEMO_EXPORT_NOT_LIVE',
          'Step 32 FULL historical validation metadata required (not smoke/live).')
    check(snap.get('total_records') == 448,
          'Step 32 full export must contain 448 disease/block/day predictions.')
    check(context.get('status') == 'HISTORICAL_CONTEXT_AND_SYNTHETIC_INCIDENCE_ONLY',
          'Step 34 climate/incidence metadata status mismatch.')
    check(context.get('estate_location_verified') is False,
          'Do not silently mark the NASA location as verified.')

    origin = pd.Timestamp(snap['forecast_origin_date']).normalize()
    check(pd.Timestamp('2025-01-01') <= origin <= pd.Timestamp('2025-12-31'),
          'This script is for 2025 historical VALIDATION snapshots only.')

    daily = pd.read_csv(weather_path, usecols=['Date', *WEATHER, 'Descriptive_Climate_Context'])
    daily['Date'] = pd.to_datetime(daily['Date'], errors='coerce')
    check(daily.Date.notna().all() and not daily.Date.duplicated().any(),
          'Climate dates invalid or duplicated.')
    hist_weather = daily.loc[(daily.Date >= origin - timedelta(days=6)) & (daily.Date <= origin)].copy()
    check(len(hist_weather) == 7 and hist_weather.Date.nunique() == 7,
          'Expected seven distinct historical NASA dates ending on forecast origin.')
    check(hist_weather[list(WEATHER)].notna().all().all(),
          'Seven-day historical NASA context has missing weather values.')
    check(pd.DatetimeIndex(hist_weather.Date).sort_values().equals(
          pd.date_range(origin - timedelta(days=6), origin, freq='D')),
          'NASA historical seven-day calendar has a gap.')
    climate_stats = {
        'start_date': (origin - timedelta(days=6)).date().isoformat(),
        'end_date': origin.date().isoformat(),
        'mean_temperature_c': round(float(hist_weather.T2M.mean()), 4),
        'mean_relative_humidity_pct': round(float(hist_weather.RH2M.mean()), 4),
        'total_rainfall_mm': round(float(hist_weather.PRECTOTCORR.sum()), 4),
        'mean_solar_allsky': round(float(hist_weather.ALLSKY_SFC_SW_DWN.mean()), 4),
        'days_with_multiple_above_reference_p90_signals': int(
            hist_weather.Descriptive_Climate_Context.eq('MULTIPLE_ABOVE_P90').sum()),
        'point_location_verified_to_estate': False,
        'interpretation': 'HISTORICAL_SINGLE_POINT_CLIMATE_CONTEXT_NOT_DISEASE_RISK',
    }
    
    # Read present/past inspection inputs ONLY. Not a single Target_* column is loaded.
    cols = ['Date', 'Disease_Name', 'Block_ID', 'Observation_Available',
            'Inspected_Bushes', 'Symptomatic_Bushes', 'Split']
    inspected = pd.read_csv(data_path, usecols=cols)
    inspected['Date'] = pd.to_datetime(inspected['Date'], errors='coerce')
    check(inspected.Date.notna().all(), 'Invalid simulated observation date.')
    inspected = inspected.loc[(inspected.Date <= origin) &
                              inspected.Disease_Name.isin(DISEASES) &
                              inspected.Split.ne('test')].copy()
    check(len(inspected) > 0, 'No historical pre-origin synthetic records.')
    for col in ('Observation_Available', 'Inspected_Bushes', 'Symptomatic_Bushes'):
        inspected[col] = pd.to_numeric(inspected[col], errors='coerce')
    valid = inspected.Observation_Available.eq(1) & inspected.Inspected_Bushes.gt(0) & \
        inspected.Symptomatic_Bushes.notna()
    observed = inspected.loc[valid].copy()
    check(len(observed) > 0, 'No valid simulated inspection records.')
    check(((observed.Symptomatic_Bushes >= 0) &
           (observed.Symptomatic_Bushes <= observed.Inspected_Bushes)).all(),
          'Invalid inspected/symptomatic bush counts.')
    check(not observed.duplicated(['Date', 'Disease_Name', 'Block_ID']).any(),
          'Duplicate simulated inspection records for same date/disease/block.')

    blocks = pd.read_csv(blocks_path)
    check({'Block_ID', 'Block_Name'}.issubset(set(blocks.columns)),
          'Estate blocks must have Block_ID and Block_Name.')
    check(len(blocks) == 16 and blocks.Block_ID.nunique() == 16,
          'Expected exactly 16 unique demo estate blocks.')

    # For each disease and block: last actually observed inspection as at origin,
    # never a zero imputed from a non-inspection day.
    latest = observed.sort_values(['Date', 'Block_ID', 'Disease_Name']).groupby(
        ['Disease_Name', 'Block_ID'], as_index=False).tail(1)
    check(latest.Disease_Name.nunique() == 4 and latest.Block_ID.nunique() == 16,
          'Not all diseases / blocks had at least one past valid observation.')
    check(len(latest) == 64, 'Expected 4 diseases x 16 blocks latest observations.')
    lookup = {(r.Disease_Name, r.Block_ID):r for r in latest.itertuples(index=False)}
    records = []
    for disease in DISEASES:
        for block in blocks.itertuples(index=False):
            k = (disease, block.Block_ID)
            check(k in lookup, f'Missing inspection: {k}')
            obs = lookup[k]
            rate = round(100 * float(obs.Symptomatic_Bushes) / float(obs.Inspected_Bushes), 4)
            age = int((origin - obs.Date).days)
            check(age >= 0, 'Found future observation.')
            records.append({
                'forecast_origin_date': origin.date().isoformat(),
                'disease_name': disease,
                'block_id': block.Block_ID,
                'block_name': block.Block_Name,
                'last_inspection_date': obs.Date.date().isoformat(),
                'days_since_inspection': age,
                'inspected_bushes': int(obs.Inspected_Bushes),
                'symptomatic_bushes': int(obs.Symptomatic_Bushes),
                'sample_incidence_pct': rate,
                'descriptive_incidence_band': incidence_band(rate),
                'observation_type': 'SIMULATED_INSPECTION_NOT_FIELD_MEASURED',
                'is_lesion_area_severity': False,
            })
    out = pd.DataFrame(records)
    check(not out.duplicated(['forecast_origin_date','disease_name','block_id']).any(),
          'Duplicate output disease/block record.')
    check((out['days_since_inspection'] >= 0).all(), 'Date leakage in output.')
    check(set(out.disease_name) == set(DISEASES), 'Disease coverage mismatch.')

    destination = base / 'climate'
    report_folder = root / 'outputs/reports'
    destination.mkdir(parents=True, exist_ok=True)
    report_folder.mkdir(parents=True, exist_ok=True)
    csv_path = destination / 'step35_block_incidence_snapshot.csv'
    json_path = destination / 'step35_historical_context_summary.json'
    report_path = report_folder / 'step35_m03_context_audit.json'
    out.to_csv(csv_path, index=False)
    metadata = {
        'step': 35,
        'status': 'PASS_HISTORICAL_SIMULATION_CONTEXT_ONLY',
        'forecast_origin_date': origin.date().isoformat(),
        'historical_climate_last_seven_days': climate_stats,
        'block_incidence_rows': len(out),
        'diseases': list(DISEASES),
        'estate_blocks': len(blocks),
        'observations_at_or_before_origin_only': True,
        'test_rows_used': False,
        'future_targets_used': False,
        'incidence_band_definition': ('Descriptive sample proportions only: 0, >0–10, '
                                      '>10–25, >25 percent. NOT calibrated agronomic severity thresholds.'),
        'records_by_band': {str(k):int(v) for k,v in out.descriptive_incidence_band.value_counts().items()},
        'inspection_age_days_max': int(out.days_since_inspection.max()),
        'dashboard_exports': {
            'block_incidence':str(csv_path.relative_to(root)),
            'historical_context':str(json_path.relative_to(root))
        },
        'limitations': [
            'This dashboard is based on historical validation-date 2025 synthetic inspections.',
            'Sample incidence percentage is NOT diseased LEAF AREA severity.',
            'Do not claim a learned or field-validated climate disease-risk model.',
            'NASA single-point coordinates (6.7789,79.9301) have not been matched to estate.',
            'Descriptive incidence bands are arbitrary display categories, NOT treatment thresholds.',
            'Historical context is end-of-day; no same-day future information may be used in start-of-day forecasts.',
            'Do not confuse historical inspection context with prospective spread forecasts.'
        ]
    }
    save_json(json_path, metadata)
    save_json(report_path, metadata)
    print('='*76)
    print('STEP 35 - m03 HISTORICAL CLIMATE + SYNTHETIC INCIDENCE CONTEXT')
    print('='*76)
    print(f'Origin: {origin.date()} | 7 historical NASA days, 4 diseases x 16 blocks = {len(out)} rows')
    print(f'Latest inspection ages: min={out.days_since_inspection.min()} max={out.days_since_inspection.max()} days')
    print(f'Climate context: mean T={climate_stats["mean_temperature_c"]} C, '
          f'RH={climate_stats["mean_relative_humidity_pct"]}%, '
          f'rainfall (7d)={climate_stats["total_rainfall_mm"]} mm')
    print(f'CSV: {csv_path}\nSummary: {json_path}\nAudit: {report_path}')
    print('PASS: No future targets, no test rows, no models trained. Source files unchanged.')
    print('WARNING: SIMULATION ONLY. NOT leaf-area severity or field-validated climate disease risk.')
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--component-root', type=Path, default=ROOT)
    args = parser.parse_args()
    run(args.component_root)


if __name__ == '__main__':
    main()
