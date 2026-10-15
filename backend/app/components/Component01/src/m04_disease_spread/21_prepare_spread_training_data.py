"""Step 21: validate and prepare the existing synthetic 7-day estate spread panel.

No targets are recomputed; no ML model is trained. Uses only information
available at end of each forecast-origin date as features.
"""
from __future__ import annotations

import json
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SYN = ROOT / 'data' / 'synthetic'
PROCESSED = ROOT / 'data' / 'processed'
REPORTS = ROOT / 'outputs' / 'reports'
CONFIGS = ROOT / 'configs'

ACTIVE_SPLITS = ['train', 'validation', 'test']
OTHER_SPLITS = ['warmup', 'gap', 'inference_only']
REQUIRED_PANEL = [
    'Date', 'Estate_ID', 'Block_ID', 'Disease_Name', 'Observation_Available',
    'Inspected_Bushes', 'Symptomatic_Bushes', 'Sample_Incidence_Pct',
    'Latest_Observed_Incidence_Pct', 'Days_Since_Last_Inspection',
    'T2M', 'RH2M', 'PRECTOTCORR', 'ALLSKY_SFC_SW_DWN',
    'Humidity_Mean_7D', 'Rainfall_Sum_7D',
    'Neighbor_Latest_Incidence_Mean_Pct', 'Neighbor_Recent_Positive_Count',
    'Forecast_Origin_Date', 'Forecast_Horizon_Days',
    'All_7_Targets_Available', 'Split'
]
BASE_FEATURES = [
    'Block_Index', 'Grid_Row', 'Grid_Column', 'Relative_Vulnerability',
    'Observation_Available', 'Inspected_Bushes', 'Symptomatic_Bushes',
    'Sample_Incidence_Pct', 'Latest_Observed_Incidence_Pct',
    'Days_Since_Last_Inspection', 'T2M', 'RH2M', 'PRECTOTCORR',
    'ALLSKY_SFC_SW_DWN', 'Humidity_Mean_7D', 'Rainfall_Sum_7D',
    'Neighbor_Latest_Incidence_Mean_Pct', 'Neighbor_Recent_Positive_Count',
    'T2M_Lag_1D', 'RH2M_Lag_1D', 'Rainfall_Lag_1D',
    'T2M_Mean_7D', 'RH2M_Mean_7D', 'Rainfall_Sum_14D',
    'Day_Of_Year_Sin', 'Day_Of_Year_Cos'
]
TARGETS = [f'Target_Disease_Active_Day_{day}' for day in range(1, 8)]
INCIDENCE_TARGETS = [f'Target_Incidence_Pct_Day_{day}' for day in range(1, 8)]
ONSET_TARGETS = [f'Target_New_Onset_By_Day_{day}' for day in range(1, 8)]


def require_columns(df: pd.DataFrame, columns: list[str], name: str) -> None:
    missing = sorted(set(columns).difference(df.columns))
    if missing:
        raise ValueError(f'{name} missing columns: {missing}')


def read_csv(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f'Required file missing: {path}')
    return pd.read_csv(path, low_memory=False)


def parse_dates(df: pd.DataFrame, cols: list[str], name: str) -> None:
    for col in cols:
        df[col] = pd.to_datetime(df[col], errors='coerce').dt.normalize()
        if df[col].isna().any():
            raise ValueError(f'{name}: invalid {col} dates ({int(df[col].isna().sum())})')


def main() -> None:
    print('=' * 76)
    print('STEP 21 - CLIMATE + ESTATE 7-DAY SPREAD TRAINING DATA (SYNTHETIC)')
    print('=' * 76)
    panel = read_csv(SYN / 'synthetic_block_records.csv')
    blocks = read_csv(SYN / 'estate_blocks.csv')
    edges = read_csv(SYN / 'block_adjacency.csv')
    obs = read_csv(SYN / 'officer_disease_observations.csv')
    climate = read_csv(PROCESSED / 'climate_daily_features.csv')
    weekly = read_csv(PROCESSED / 'climate_weekly_summary.csv')

    require_columns(panel, REQUIRED_PANEL, 'synthetic_block_records.csv')
    for day in range(1, 8):
        require_columns(panel, [f'Target_Date_Day_{day}', TARGETS[day - 1],
                                INCIDENCE_TARGETS[day - 1], ONSET_TARGETS[day - 1]], 'synthetic panel')
    require_columns(blocks, ['Block_ID', 'Grid_Row', 'Grid_Column', 'Relative_Vulnerability'], 'estate_blocks.csv')
    require_columns(edges, ['Source_Block', 'Target_Block', 'Relationship'], 'block_adjacency.csv')
    require_columns(obs, ['Observation_ID', 'Date', 'Block_ID', 'Inspected_Bushes', 'Symptomatic_Bushes', 'Observation_Source'], 'officer observations')
    require_columns(weekly, ['Week_Start', 'Complete_Week'], 'climate_weekly_summary.csv')
    if 'Date' not in climate.columns:
        raise ValueError('Step 20 daily features missing Date column. Inspect climate_daily_features.csv headers.')
    require_columns(climate, ['Date', 'T2M', 'RH2M', 'PRECTOTCORR', 'ALLSKY_SFC_SW_DWN'], 'climate_daily_features.csv')
    parse_dates(panel, ['Date', 'Forecast_Origin_Date'], 'panel')
    # Forecast target dates may be blank in inference-only records.
    for i in range(1, 8):
        c = f'Target_Date_Day_{i}'
        panel[c] = pd.to_datetime(panel[c], errors='coerce').dt.normalize()
    parse_dates(climate, ['Date'], 'daily climate')
    parse_dates(obs, ['Date'], 'observations')

    if len(panel) == 0 or panel.duplicated(['Date', 'Block_ID']).any():
        raise ValueError('Empty panel or duplicated Date + Block_ID keys')
    if not panel['Date'].eq(panel['Forecast_Origin_Date']).all():
        raise ValueError('Date differs from Forecast_Origin_Date; stop to investigate.')
    if not pd.to_numeric(panel['Forecast_Horizon_Days'], errors='coerce').eq(7).all():
        raise ValueError('Expected Forecast_Horizon_Days==7 for all rows.')
    for day in range(1, 8):
        dates = panel[f'Target_Date_Day_{day}']
        is_labeled = panel['Split'].isin(ACTIVE_SPLITS)
        dates_ok = dates.eq(panel['Date'] + pd.Timedelta(days=day))
        # Unlabeled inference-only dates may be absent, but any supplied date must align.
        invalid = (~dates_ok) & (is_labeled | dates.notna())
        if invalid.any():
            raise ValueError(f'Day {day} target-date alignment errors: {int(invalid.sum())}')
    allowed_splits = set(ACTIVE_SPLITS + OTHER_SPLITS)
    counts = {str(k): int(v) for k, v in panel['Split'].value_counts().to_dict().items()}
    if set(counts) - allowed_splits:
        raise ValueError(f'Unexpected split labels: {sorted(set(counts)-allowed_splits)}')
    if any(counts.get(split, 0) == 0 for split in ACTIVE_SPLITS):
        raise ValueError('Expected nonempty train, validation and test partitions.')
    # Split assignment should be global per date, not different for adjacent blocks.
    if (panel.groupby('Date')['Split'].nunique() > 1).any():
        raise ValueError('Split differs across blocks on the same Date.')
    for a, b in [('train', 'validation'), ('validation', 'test')]:
        if panel.loc[panel['Split'].eq(a), 'Date'].max() >= panel.loc[panel['Split'].eq(b), 'Date'].min():
            raise ValueError(f'Split chronology violated: {a} vs {b}')
    # Ensure horizon target periods of adjacent partitions do not overlap forecast origins.
    for a, b in [('train', 'validation'), ('validation', 'test')]:
        prior_last_target = panel.loc[panel['Split'].eq(a), 'Date'].max() + pd.Timedelta(days=7)
        next_first_origin = panel.loc[panel['Split'].eq(b), 'Date'].min()
        if prior_last_target >= next_first_origin:
            raise ValueError(f'7-day horizon overlap across {a} -> {b}; require time gap.')

    blocks = blocks.copy()
    if blocks['Block_ID'].isna().any() or blocks['Block_ID'].duplicated().any():
        raise ValueError('Duplicate/blank Block_ID in estate_blocks.csv')
    block_ids = sorted(blocks['Block_ID'].astype(str).tolist())
    id_map = {block: i for i, block in enumerate(block_ids)}
    if set(panel['Block_ID'].astype(str)) - set(id_map):
        raise ValueError('Panel refers to blocks missing from estate_blocks.csv')
    if set(edges['Source_Block'].astype(str)).union(set(edges['Target_Block'].astype(str))) - set(id_map):
        raise ValueError('Adjacency refers to unknown blocks')
    if edges.duplicated(['Source_Block', 'Target_Block']).any():
        raise ValueError('Duplicate directed adjacency edge')
    edges_out = edges.copy()
    edges_out['Source_Index'] = edges_out['Source_Block'].map(id_map)
    edges_out['Target_Index'] = edges_out['Target_Block'].map(id_map)
    if obs['Observation_ID'].duplicated().any():
        raise ValueError('Duplicate Observation_ID detected')
    if set(obs['Block_ID'].astype(str)) - set(id_map):
        raise ValueError('Observation refers to unknown block')
    if (pd.to_numeric(obs['Symptomatic_Bushes'], errors='coerce') > pd.to_numeric(obs['Inspected_Bushes'], errors='coerce')).any():
        raise ValueError('Some observations have symptomatic bushes > inspected bushes')

    climate = climate.sort_values('Date').copy()
    if climate['Date'].duplicated().any():
        raise ValueError('Duplicate Date in Step 20 climate daily output.')
    for c in ['T2M', 'RH2M', 'PRECTOTCORR', 'ALLSKY_SFC_SW_DWN']:
        climate[c] = pd.to_numeric(climate[c], errors='coerce').replace(-999, np.nan)
    # Historical, origin-day features. No calendar-week sums from the current incomplete week.
    climate['T2M_Lag_1D'] = climate['T2M'].shift(1)
    climate['RH2M_Lag_1D'] = climate['RH2M'].shift(1)
    climate['Rainfall_Lag_1D'] = climate['PRECTOTCORR'].shift(1)
    climate['T2M_Mean_7D'] = climate['T2M'].rolling(7, min_periods=7).mean()
    climate['RH2M_Mean_7D'] = climate['RH2M'].rolling(7, min_periods=7).mean()
    climate['Rainfall_Sum_14D'] = climate['PRECTOTCORR'].rolling(14, min_periods=14).sum()
    climate_features = ['T2M_Lag_1D', 'RH2M_Lag_1D', 'Rainfall_Lag_1D',
                        'T2M_Mean_7D', 'RH2M_Mean_7D', 'Rainfall_Sum_14D']
    check_climate = ['Date', 'T2M', 'RH2M', 'PRECTOTCORR', 'ALLSKY_SFC_SW_DWN'] + climate_features
    climate_join = climate[check_climate].rename(columns={c: f'NASA_{c}' for c in ['T2M', 'RH2M', 'PRECTOTCORR', 'ALLSKY_SFC_SW_DWN']})
    dataset = panel.merge(blocks[['Block_ID', 'Grid_Row', 'Grid_Column', 'Relative_Vulnerability']],
                          on='Block_ID', how='left', validate='many_to_one')
    dataset = dataset.merge(climate_join, on='Date', how='left', validate='many_to_one')
    if dataset[climate_features].isna().any().any():
        missing = dataset[climate_features].isna().sum().to_dict()
        raise ValueError(f'Historical climate features unavailable on panel dates: {missing}')
    weather_checks = {}
    for c in ['T2M', 'RH2M', 'PRECTOTCORR', 'ALLSKY_SFC_SW_DWN']:
        original = pd.to_numeric(dataset[c], errors='coerce')
        reference = dataset[f'NASA_{c}']
        if original.isna().any() or reference.isna().any():
            raise ValueError(f'{c} has unavailable source or NASA values.')
        absdiff = (original - reference).abs()
        weather_checks[c] = {'max_absolute_difference': float(absdiff.max()),
                             'rows_different_gt_0_05': int((absdiff > 0.05).sum())}
    # Keep original climate attributes from the synthetic panel. Report source differences,
    # never silently rewrite generated block features with an unknown site or new values.
    dataset = dataset.drop(columns=[f'NASA_{c}' for c in ['T2M', 'RH2M', 'PRECTOTCORR', 'ALLSKY_SFC_SW_DWN']])
    dataset['Block_Index'] = dataset['Block_ID'].map(id_map)
    day_of_year = dataset['Date'].dt.dayofyear
    dataset['Day_Of_Year_Sin'] = np.sin(2 * np.pi * day_of_year / 365.25)
    dataset['Day_Of_Year_Cos'] = np.cos(2 * np.pi * day_of_year / 365.25)
    for c in BASE_FEATURES:
        dataset[c] = pd.to_numeric(dataset[c], errors='coerce')
    if not np.isfinite(dataset[BASE_FEATURES].to_numpy(dtype=float)).all():
        raise ValueError('One or more feature columns have missing/nonfinite values; do not silently fill.')
    if any('Target_' in c or 'Split' in c or 'Forecast' in c for c in BASE_FEATURES):
        raise RuntimeError('Feature leakage: a target or split column entered feature list!')

    active = dataset.loc[dataset['Split'].isin(ACTIVE_SPLITS)].copy()
    if not pd.to_numeric(active['All_7_Targets_Available'], errors='coerce').eq(1).all():
        raise ValueError('Missing seven-day ground truth in train/validation/test rows.')
    all_outcomes = TARGETS + INCIDENCE_TARGETS + ONSET_TARGETS
    for c in all_outcomes:
        active[c] = pd.to_numeric(active[c], errors='coerce')
        if active[c].isna().any():
            raise ValueError(f'Active split contains missing target: {c}')
    for c in TARGETS + ONSET_TARGETS:
        if not active[c].isin([0, 1]).all():
            raise ValueError(f'Nonbinary target found in {c}')
    for c in INCIDENCE_TARGETS:
        if not active[c].between(0, 100).all():
            raise ValueError(f'Incidence target outside 0..100: {c}')
    obs_count = int(len(obs))
    dataset.sort_values(['Date', 'Block_Index'], inplace=True)
    active.sort_values(['Date', 'Block_Index'], inplace=True)
    meta_cols = ['Date', 'Estate_ID', 'Block_ID', 'Disease_Name', 'Split']
    for p in (PROCESSED, REPORTS, CONFIGS):
        p.mkdir(parents=True, exist_ok=True)
    panel_path = PROCESSED / 'spread_model_panel_step21.csv'
    supervised_path = PROCESSED / 'spread_supervised_step21.csv'
    inference_path = PROCESSED / 'spread_inference_step21.csv'
    graph_path = PROCESSED / 'spread_graph_edges_step21.csv'
    # Wide panel is for auditing. For training only the explicit feature/label contract is used.
    dataset.to_csv(panel_path, index=False, date_format='%Y-%m-%d')
    active[meta_cols + BASE_FEATURES + all_outcomes].to_csv(supervised_path, index=False, date_format='%Y-%m-%d')
    inference = dataset.loc[dataset['Split'].eq('inference_only'), meta_cols + BASE_FEATURES]
    inference.to_csv(inference_path, index=False, date_format='%Y-%m-%d')
    edges_out.to_csv(graph_path, index=False)
    contract = {
        'step': 21, 'dataset_status': 'SYNTHETIC_DEMONSTRATION_NOT_FIELD_VALIDATED',
        'forecast_origin_definition': 'End of observation Date; features include climate of Date but none from future days.',
        'split_method': 'Preserved existing date-based splits; gap/warmup/inference_only excluded from supervised fitting/evaluation.',
        'forecast_horizons_days': list(range(1, 8)),
        'features': BASE_FEATURES, 'classification_targets': TARGETS,
        'incidence_targets': INCIDENCE_TARGETS, 'onset_targets': ONSET_TARGETS,
        'block_index_mapping': id_map, 'splits_for_training': ACTIVE_SPLITS,
        'graph_edge_columns': ['Source_Index', 'Target_Index'],
        'limitations': ['Estate blocks and officer observations are synthetic.',
                        'NASA POWER is one spatial point; plantation correspondence unverified.',
                        'Current-day weather is available only for end-of-day forecasting.',
                        'Calendar-week summaries must not be joined as predictors before week end.',
                        'No real-world spread model validation has occurred.']
    }
    contract_path = CONFIGS / 'step21_spread_feature_contract.json'
    contract_path.write_text(json.dumps(contract, indent=2), encoding='utf-8')
    report = {
        'status': 'PASS_SYNTHETIC_DATA_INTEGRITY_ONLY',
        'panel_rows': int(len(panel)), 'supervised_rows': int(len(active)),
        'inference_only_rows': int(len(inference)), 'estate_blocks': int(len(blocks)),
        'directed_graph_edges': int(len(edges)), 'officer_observation_rows': obs_count,
        'split_counts': counts, 'weather_alignment_checks': weather_checks,
        'earliest_panel_origin': str(dataset['Date'].min().date()),
        'latest_panel_origin': str(dataset['Date'].max().date()),
        'feature_count': len(BASE_FEATURES),
        'climate_source_location': 'NASA POWER 6.7789,79.9301; estate match UNVERIFIED',
        'next': 'Train baseline supervised models using only step21_spread_feature_contract.json feature list; preserve validation/test.'
    }
    report_path = REPORTS / 'step21_climate_estate_alignment.json'
    report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')

    print(f'Panel rows: {len(dataset)} | Supervised: {len(active)} | Inference-only: {len(inference)}')
    print(f'Blocks: {len(blocks)} | Directed adjacency edges: {len(edges)} | Synthetic observations: {obs_count}')
    print(f'Splits: {counts}')
    print(f'Feature count: {len(BASE_FEATURES)} | Day-ahead targets: 1 to 7')
    mismatch_counts = {k: v["rows_different_gt_0_05"] for k, v in weather_checks.items()}
    print(f"Climate align differences >0.05: {mismatch_counts}")
    print(f'Supervised CSV: {supervised_path}')
    print(f'Graph edges: {graph_path}')
    print(f'Feature contract: {contract_path}')
    print(f'Report: {report_path}')
    print('PASS: feature integrity and time split checks completed; NO models trained.')
    print('CAUTION: synthetic estate/observations, and NASA site-to-estate match unverified.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'STEP 21 FAILED: {type(exc).__name__}: {exc}', file=sys.stderr)
        sys.exit(1)
