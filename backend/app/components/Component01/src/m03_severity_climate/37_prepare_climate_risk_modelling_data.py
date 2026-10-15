#!/usr/bin/env python3
"""Step 37: leakage-audited climate-associated SYNTHETIC disease risk training tables.

This is data preparation, NOT model training. Uses past/as-of-day-end NASA features
and future synthetic day-7 labels. Single NASA location is NOT verified to Nuwara Eliya.
No field-validated climate risk or leaf-lesion severity is computed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_ROOT = Path(__file__).resolve().parents[2]
DISEASES = ('Brown Blight', 'Grey Leaf', 'Red Rust', 'Red Spider Mite')
SPLITS = ('train', 'validation', 'test')
DAY_WEATHER = ('T2M', 'RH2M', 'PRECTOTCORR', 'ALLSKY_SFC_SW_DWN')
WEATHER_FEATURES = (
    'T2M', 'RH2M', 'PRECTOTCORR', 'ALLSKY_SFC_SW_DWN',
    'T2M_Mean_7D', 'RH2M_Mean_7D', 'Rainfall_Sum_7D', 'Solar_Mean_7D',
    'T2M_Mean_14D', 'RH2M_Mean_14D', 'Rainfall_Sum_14D', 'Solar_Mean_14D',
)
SEASON_FEATURES = ('Day_Of_Year_Sin', 'Day_Of_Year_Cos')
ONEHOT = ('Disease_brown_blight', 'Disease_grey_leaf', 'Disease_red_rust', 'Disease_red_spider_mite')
FEATURES = (*WEATHER_FEATURES, *SEASON_FEATURES, *ONEHOT)
TARGETS = ('Target_Disease_Active_Day_7', 'Target_New_Onset_By_Day_7')
METADATA = ('Forecast_Origin_Date', 'Forecast_Target_Date', 'Block_ID', 'Disease_Name', 'Split')


def ensure(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def required(frame: pd.DataFrame, columns: tuple[str, ...] | list[str], name: str) -> None:
    absent = sorted(set(columns) - set(frame.columns))
    ensure(not absent, f'{name}: missing required columns: {absent}')


def date_column(frame: pd.DataFrame, name: str, source: str) -> None:
    frame[name] = pd.to_datetime(frame[name], errors='coerce')
    ensure(frame[name].notna().all(), f'{source}: missing/invalid {name}')
    ensure((frame[name] == frame[name].dt.normalize()).all(), f'{source}: {name} must be whole dates')


def load_climate(path: Path) -> pd.DataFrame:
    ensure(path.is_file(), f'Step 20 climate file missing: {path}')
    columns = ['Date', *WEATHER_FEATURES]
    climate = pd.read_csv(path, usecols=lambda name: name in columns)
    required(climate, columns, 'Step 20 daily climate')
    date_column(climate, 'Date', 'climate')
    ensure(not climate.Date.duplicated().any(), 'Duplicate dates in Step 20 climate')
    climate = climate.sort_values('Date').reset_index(drop=True)
    for column in WEATHER_FEATURES:
        climate[column] = pd.to_numeric(climate[column], errors='coerce').replace(-999, np.nan)
    ensure(climate[list(DAY_WEATHER)].notna().all().all(),
           'Required NASA daily columns have missing values')
    # Window calculations were performed historically by Step 20. Here we
    # re-check a representative recent window exactly (no future rows).
    for window in (7, 14):
        for origin, base, operation in (
            ('T2M_Mean', 'T2M', 'mean'), ('RH2M_Mean', 'RH2M', 'mean'),
            ('Rainfall_Sum', 'PRECTOTCORR', 'sum'),
            ('Solar_Mean', 'ALLSKY_SFC_SW_DWN', 'mean'),
        ):
            name = f'{origin}_{window}D'
            rederived = (climate[base].rolling(window, min_periods=window).mean()
                         if operation == 'mean' else climate[base].rolling(window, min_periods=window).sum())
            known = climate[name].notna()
            ensure(np.allclose(climate.loc[known, name], rederived.loc[known],
                               rtol=0, atol=1e-5), f'Climate rolling feature is not trailing-only: {name}')
    return climate


def load_simulation(path: Path) -> tuple[pd.DataFrame, dict]:
    ensure(path.is_file(), f'Step 23 synthetic dataset missing: {path}')
    columns = [
        'Date', 'Forecast_Origin_Date', 'Target_Date_Day_7', 'Block_ID',
        'Disease_Name', 'Split', 'All_7_Targets_Available',
        'Climate_Source', 'Observation_Source', *DAY_WEATHER, *TARGETS,
    ]
    sim = pd.read_csv(path, usecols=lambda name: name in columns)
    required(sim, columns, 'Step 23 synthetic records')
    all_counts = {str(k): int(v) for k, v in sim['Split'].value_counts().items()}
    ensure(set(SPLITS).issubset(set(all_counts)), 'Missing a chronological train/validation/test split')
    ensure(set(sim.Disease_Name.unique()) == set(DISEASES), 'Expected exactly the four synthetic diseases')
    ensure(sim.Climate_Source.eq('NASA_POWER_SINGLE_POINT').all(),
           'Expected single-point NASA synthetic climate source')
    ensure(sim.Observation_Source.isin(('SYNTHETIC_FIELD_SIMULATION',
                                      'SYNTHETIC_MULTIDISEASE_SCENARIO_V1')).all(),
           'Unexpected data provenance: require synthetic observation source')
    ensure(set(sim.loc[sim.Disease_Name.eq('Red Rust'), 'Observation_Source']) ==
           {'SYNTHETIC_FIELD_SIMULATION'}, 'Red Rust source provenance mismatch')
    ensure(set(sim.loc[sim.Disease_Name.ne('Red Rust'), 'Observation_Source']) ==
           {'SYNTHETIC_MULTIDISEASE_SCENARIO_V1'},
           'Generated three-disease scenario provenance mismatch')
    # Ignore all warmup, embargo (gap) and inference_only records: do not
    # leak from embargo data into model-fitting rows.
    sim = sim.loc[sim.Split.isin(SPLITS)].copy()
    for date in ('Date', 'Forecast_Origin_Date', 'Target_Date_Day_7'):
        date_column(sim, date, 'synthetic records')
    ensure(sim['Date'].eq(sim['Forecast_Origin_Date']).all(),
           'Forecast origin not aligned with synthetic Date')
    ensure((sim.Target_Date_Day_7 - sim.Date).dt.days.eq(7).all(),
           'Target_Day_7 not exactly seven days after origin')
    ensure(pd.to_numeric(sim.All_7_Targets_Available, errors='coerce').eq(1).all(),
           'A selected row lacks valid day-7 target availability')
    for target in TARGETS:
        sim[target] = pd.to_numeric(sim[target], errors='coerce')
        ensure(sim[target].notna().all() and sim[target].isin([0, 1]).all(),
               f'{target}: must be available binary labels')
    ensure(not sim.duplicated(['Date', 'Disease_Name', 'Block_ID']).any(),
           'Repeated disease/block/origin keys in simulation')
    ensure(sim.Block_ID.nunique() == 16, 'Expected exactly 16 simulated blocks')
    ensure(not sim.Block_ID.isna().any(), 'Missing block ID')

    bounds = {}
    for split in SPLITS:
        part = sim.loc[sim.Split.eq(split)]
        ensure(part.Disease_Name.nunique() == 4 and part.Block_ID.nunique() == 16,
               f'{split}: incomplete disease/block coverage')
        per_origin = part.groupby('Date', sort=False).size()
        ensure(per_origin.eq(64).all(),
               f'{split}: expected all 4 diseases x 16 blocks on each origin')
        bounds[split] = {
            'rows': int(len(part)),
            'unique_origins': int(part.Date.nunique()),
            'first_origin': part.Date.min().date().isoformat(),
            'last_origin': part.Date.max().date().isoformat(),
            'last_target_day_7': part.Target_Date_Day_7.max().date().isoformat(),
        }
    for earlier, later in (('train', 'validation'), ('validation', 'test')):
        a = pd.Timestamp(bounds[earlier]['last_target_day_7'])
        b = pd.Timestamp(bounds[later]['first_origin'])
        ensure(a < b, f'Chronological split/target overlap: {earlier} -> {later}')
    return sim, {'original_split_counts': all_counts, 'used_split_boundaries': bounds}


def build(root: Path) -> dict:
    root = root.resolve()
    climate_path = root / 'data/processed/climate_daily_features.csv'
    source_path = root / 'data/synthetic/synthetic_block_records_multidisease.csv'
    climate_meta_path = root / 'outputs/reports/step20_nasa_climate_quality.json'
    ensure(climate_meta_path.is_file(), 'Required Step 20 audit missing')
    source_meta = json.loads(climate_meta_path.read_text(encoding='utf-8'))
    ensure(source_meta.get('status') == 'HISTORICAL_CLIMATE_PREPROCESSED_NOT_DISEASE_MODEL',
           'Step 20 metadata was not verified')
    climate = load_climate(climate_path)
    sim, split_info = load_simulation(source_path)
    source_weather = sim[['Date', *DAY_WEATHER]].drop_duplicates()
    ensure(not source_weather.Date.duplicated().any(),
           'Conflicting NASA values for the same synthetic date')
    verified = source_weather.merge(climate[['Date', *DAY_WEATHER]],
                                    on='Date', how='left', validate='one_to_one',
                                    suffixes=('_synthetic', '_step20'), indicator=True)
    ensure(verified['_merge'].eq('both').all(), 'NASA climate dates missing for simulation')
    for column in DAY_WEATHER:
        a = pd.to_numeric(verified[f'{column}_synthetic'], errors='coerce')
        b = verified[f'{column}_step20']
        ensure(a.notna().all() and b.notna().all(), f'Unusable synthetic NASA {column}')
        ensure(np.allclose(a, b, atol=1e-4, rtol=0),
               f'Synthetic daily climate differs from historical NASA source: {column}')

    # Use Step 20 ORIGINAL climate features, NOT simulated future weather.
    labels = sim[['Date', 'Target_Date_Day_7', 'Disease_Name', 'Block_ID', 'Split', *TARGETS]].copy()
    prepared = labels.merge(climate[['Date', *WEATHER_FEATURES]], on='Date',
                            how='left', validate='many_to_one', indicator=True)
    ensure(prepared['_merge'].eq('both').all(), 'Missing source climate for at least one origin')
    prepared.drop(columns=['_merge'], inplace=True)
    ensure(prepared[list(WEATHER_FEATURES)].notna().all().all(),
           'Climate feature missing for model-ready split dates')
    doy = prepared['Date'].dt.dayofyear.to_numpy()
    prepared['Day_Of_Year_Sin'] = np.sin(2 * np.pi * doy / 365.25)
    prepared['Day_Of_Year_Cos'] = np.cos(2 * np.pi * doy / 365.25)
    onehot_names = dict(zip(DISEASES, ONEHOT))
    for disease, name in onehot_names.items():
        prepared[name] = prepared['Disease_Name'].eq(disease).astype('int8')
    ensure(prepared[list(FEATURES)].replace([np.inf, -np.inf], np.nan).notna().all().all(),
           'Some feature values are invalid/nonfinite')
    prepared.rename(columns={'Date':'Forecast_Origin_Date',
                             'Target_Date_Day_7':'Forecast_Target_Date'}, inplace=True)
    # Date, block IDs and outcomes are always retained as *metadata/targets*,
    # never features. Same-day NASA values require end-of-day inference.
    prepared = prepared[[*METADATA, *FEATURES, *TARGETS]]
    ensure(len(prepared) == sum(split_info['used_split_boundaries'][s]['rows'] for s in SPLITS),
           'Join unexpectedly changed row count')

    output_dir = root / 'data/processed'
    report_dir = root / 'outputs/reports'
    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for split in SPLITS:
        file = output_dir / ('climate_risk_step37_' + ('test_LOCKED' if split == 'test' else split) + '.csv')
        frame = prepared.loc[prepared.Split.eq(split)].sort_values(
            ['Forecast_Origin_Date','Disease_Name','Block_ID']).reset_index(drop=True)
        frame['Forecast_Origin_Date'] = frame.Forecast_Origin_Date.dt.strftime('%Y-%m-%d')
        frame['Forecast_Target_Date'] = frame.Forecast_Target_Date.dt.strftime('%Y-%m-%d')
        frame.to_csv(file, index=False, float_format='%.8g')
        paths[split] = str(file.relative_to(root))

    contract_path = output_dir / 'climate_risk_step37_contract.json'
    report_path = report_dir / 'step37_m03_climate_risk_data_audit.json'
    disease_summary = []
    for (split, disease), group in prepared.groupby(['Split','Disease_Name']):
        disease_summary.append({
            'split': split, 'disease': disease, 'rows': int(len(group)),
            'day7_active_positive_rate': round(float(group[TARGETS[0]].mean()), 6),
            'by_day7_new_onset_positive_rate': round(float(group[TARGETS[1]].mean()), 6)
        })
    contract = {
        'schema_version':'step37-v1', 'step':37,
        'status':'PASS_READY_FOR_SIMULATION_CLIMATE_RISK_MODEL_TRAINING_NOT_TRAINED',
        'scope':'SYNTHETIC four-disease risk proxies with historical NASA POWER climate',
        'origin_semantics':'END_OF_DAY; same-day observed climate is available before prediction',
        'forecast_horizon_days':7,
        'features':list(FEATURES), 'feature_count':len(FEATURES),
        'metadata_columns':list(METADATA), 'targets':list(TARGETS),
        'binary_target_definitions':{
            TARGETS[0]:'Synthetic disease activity on forecast origin + 7 days (0/1)',
            TARGETS[1]:'Synthetic new-onset-by-day-7 indicator (0/1, synthetic scenario definition)',
        },
        'diseases':list(DISEASES), 'blocks':16,
        'source_daily_climate':str(climate_path.relative_to(root)),
        'source_synthetic_scenarios':str(source_path.relative_to(root)),
        'nasa_point_latitude':source_meta.get('latitude', 6.7789),
        'nasa_point_longitude':source_meta.get('longitude', 79.9301),
        'target_region': 'Nuwara Eliya (user-provided intent; exact estate unknown)',
        'nasa_location_verified_for_target_estate':False,
        'feature_interpretation':'One date-specific climate exposure shared by all 16 blocks; no block-specific climate differentiation.',
        'source_data_check':'Synthetic daily climate equal to Step20 climate daily values (within 0.0001)',
        'training_rules':{
            'train_only_fit':'Fit ML/preprocessing/calibration on train only; use validation for selection.',
            'test_policy':'test_LOCKED is only for one final evaluation after all tuning/model selection.',
            'no_future_predictors':'Never use Target_*, targets, future NASA weather, or forecast target date as predictors.',
            'no_random_split':'Respect historical 7-day-separated split boundaries.',
            'metrics':'Report validation ROC-AUC and PR-AUC where valid, Brier/log-loss and baseline, disease-specific metrics; evaluate 16 same-day blocks as correlated, not independent climate observations.',
            'dynamic_api':'Climate background estimate may be shared across blocks for a date/disease. Step 42 block-specific officer updates must be processed in m04, not claimed to change shared climate weather.'
        },
        'outputs':paths,
        'known_limitations':[
            'Training labels and officer observations are simulated; no disease model field validation.',
            'NASA data point (6.7789,79.9301) is not matched to an estate in Nuwara Eliya; results are not Nuwara Eliya-specific.',
            'Climate-related associations are not causal disease effects.',
            'Climate weather is single-point and identical for all 16 dummy estate blocks.',
            'No lesion segmentation or leaf-area severity is provided by this dataset.',
            'Step37 prepares data only, does not train, evaluate or save any ML models.',
            'Training outcomes include repeated correlated blocks for a given date; interpret accuracy carefully.',
        ],
    }
    contract_path.write_text(json.dumps(contract, indent=2, allow_nan=False), encoding='utf-8')
    audit = {**contract, 'original_split_counts':split_info['original_split_counts'],
             'used_split_boundaries':split_info['used_split_boundaries'],
             'records_prepared':int(len(prepared)), 'weather_source_dates_checked':int(len(verified)),
             'per_disease_split_prevalence':disease_summary,
             'validation_only_expected_until_step38':True,
             'contract':str(contract_path.relative_to(root))}
    report_path.write_text(json.dumps(audit, indent=2, allow_nan=False), encoding='utf-8')
    print('='*77)
    print('STEP 37 - CLIMATE-ASSOCIATED DISEASE RISK DATA | SYNTHETIC TRAINING PREP')
    print('='*77)
    print('Rows:', len(prepared), '| Features:', len(FEATURES), '| Targets:', len(TARGETS))
    for split in SPLITS:
        info = split_info['used_split_boundaries'][split]
        print(f'  {split:10s} rows={info["rows"]:5d} dates={info["unique_origins"]:3d} '
              f'{info["first_origin"]} to {info["last_origin"]}')
    print('Diseases:', ', '.join(DISEASES), '| Blocks:', prepared.Block_ID.nunique())
    print('NASA climate dates cross-checked:', len(verified))
    print('Climate location: 6.7789,79.9301 | NOT verified as Nuwara Eliya estate')
    print('Train:', root / paths['train'])
    print('Validation:', root / paths['validation'])
    print('Locked test:', root / paths['test'])
    print('Contract:', contract_path)
    print('Audit:', report_path)
    print('PASS: Leakage-aware simulation dataset prepared. NO MODEL TRAINED.')
    print('WARNING: synthetic targets and unverified climate location; NOT real-estate accuracy.')
    return audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--component-root', default=str(DEFAULT_ROOT), type=Path)
    args = parser.parse_args()
    build(args.component_root)


if __name__ == '__main__':
    main()
