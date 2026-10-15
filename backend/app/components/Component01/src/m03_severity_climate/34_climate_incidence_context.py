#!/usr/bin/env python3
"""Step 34 — historical NASA climate context and synthetic observed-incidence summaries.

NO trained climate disease-risk model, NO image lesion-area severity estimates.
Uses historical (2011–2022) MONTH-SPECIFIC descriptive reference thresholds.
The climate signal is context, NOT a disease probability or agronomic diagnosis.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
WEATHER = ['T2M', 'RH2M', 'PRECTOTCORR', 'ALLSKY_SFC_SW_DWN']
THRESHOLD_REFERENCE_END = '2022-12-31'


def require_columns(df: pd.DataFrame, required: list[str], source: str) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f'{source} missing required columns: {missing}')


def clean_daily(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    require_columns(df, ['Date', *WEATHER], str(path))
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    if df['Date'].isna().any() or df['Date'].duplicated().any():
        raise ValueError('NASA daily features have invalid/duplicate Date values')
    df = df.sort_values('Date').reset_index(drop=True)
    for c in WEATHER:
        df[c] = pd.to_numeric(df[c], errors='coerce').replace(-999, np.nan)
    return df


def build_climate_context(daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    df = daily[['Date', *WEATHER]].copy()
    df['Month'] = df['Date'].dt.month
    ref = df.loc[df['Date'] <= pd.Timestamp(THRESHOLD_REFERENCE_END)].copy()
    if len(ref) < 365 * 2:
        raise ValueError('Insufficient historical baseline before 2023')
    # Reference is historical and month-specific; never fit on 2023+ simulated outcomes.
    quantiles = ref.groupby('Month')[WEATHER].quantile(0.9)
    if len(quantiles) != 12 or quantiles.isna().any().any():
        raise ValueError('Insufficient complete monthly reference values')
    q = {str(m): {k: round(float(quantiles.loc[m, k]), 5) for k in WEATHER} for m in range(1,13)}
    for var, name in [('T2M','temp'),('RH2M','humidity'),('PRECTOTCORR','rainfall'),('ALLSKY_SFC_SW_DWN','solar')]:
        t = df['Month'].map(quantiles[var])
        df[f'{name}_above_reference_p90'] = np.where(df[var].notna(), (df[var] > t).astype(int), np.nan)
    flags = [c for c in df if c.endswith('_above_reference_p90')]
    df['Climate_Data_Complete'] = df[WEATHER].notna().all(axis=1)
    df['Historical_High_Signal_Count'] = df[flags].sum(axis=1).where(df['Climate_Data_Complete'])
    # Descriptive only. More extremes need not mean more disease.
    df['Descriptive_Climate_Context'] = np.select(
        [df['Historical_High_Signal_Count'] >= 2, df['Historical_High_Signal_Count'] == 1,
         df['Historical_High_Signal_Count'] == 0],
        ['MULTIPLE_ABOVE_P90','ONE_ABOVE_P90','NONE_ABOVE_P90'], default='MISSING_WEATHER')
    df['Reference'] = 'MONTH_SPECIFIC_2011_2022_P90_DESCRIPTIVE_NOT_DISEASE_RISK'

    monthly = (df.assign(Year_Month=df.Date.dt.to_period('M').astype(str))
       .groupby('Year_Month', as_index=False).agg(
          Available_Days=('Date','size'),
          Complete_Days=('Climate_Data_Complete','sum'),
          Temperature_Mean_C=('T2M','mean'),
          Humidity_Mean_Pct=('RH2M','mean'),
          Rainfall_Total_Mm=('PRECTOTCORR','sum'),
          Solar_Mean=('ALLSKY_SFC_SW_DWN','mean'),
          Days_With_Multiple_High_Signals=('Descriptive_Climate_Context', lambda s: int((s=='MULTIPLE_ABOVE_P90').sum()))))
    # Label incomplete calendar months; partial month totals are not full-month totals.
    month_dates = pd.to_datetime(monthly['Year_Month'] + '-01')
    monthly['Calendar_Days_In_Month'] = month_dates.dt.days_in_month
    monthly['Month_Complete'] = ((monthly.Available_Days == monthly.Calendar_Days_In_Month) &
                                 (monthly.Complete_Days == monthly.Calendar_Days_In_Month)).astype(int)
    monthly.loc[monthly.Month_Complete != 1, 'Rainfall_Total_Mm'] = np.nan
    return df, monthly, q


def build_incidence_summary(path: Path) -> tuple[pd.DataFrame, dict]:
    if not path.is_file():
        raise FileNotFoundError(f'Multi-disease simulated observations missing: {path}')
    use = ['Date','Disease_Name','Block_ID','Observation_Available','Inspected_Bushes','Symptomatic_Bushes']
    # Only present-day simulated inspection counts; future label columns intentionally NOT loaded.
    data = pd.read_csv(path, usecols=use)
    data['Date'] = pd.to_datetime(data['Date'], errors='coerce')
    if data['Date'].isna().any():
        raise ValueError('Synthetic observations contain invalid dates')
    for field in ['Observation_Available','Inspected_Bushes','Symptomatic_Bushes']:
        data[field] = pd.to_numeric(data[field], errors='coerce')
    valid = data['Observation_Available'].eq(1) & data['Inspected_Bushes'].gt(0) & data['Symptomatic_Bushes'].notna()
    observed = data.loc[valid].copy()
    if observed.empty:
        raise ValueError('No simulated inspected-bush records available')
    if (observed['Symptomatic_Bushes'] < 0).any() or (observed['Symptomatic_Bushes'] > observed['Inspected_Bushes']).any():
        raise ValueError('Simulated symptomatic counts exceed inspected counts or are negative')
    observed['Year_Month'] = observed['Date'].dt.to_period('M').astype(str)
    grouped = (observed.groupby(['Year_Month','Disease_Name'], as_index=False)
        .agg(Inspections=('Block_ID','size'), Unique_Blocks=('Block_ID','nunique'),
             Inspected_Bushes=('Inspected_Bushes','sum'), Symptomatic_Bushes=('Symptomatic_Bushes','sum')))
    grouped['Weighted_Sample_Incidence_Pct'] = (100 * grouped.Symptomatic_Bushes / grouped.Inspected_Bushes).round(4)
    grouped['Data_Provenance'] = 'SYNTHETIC_FIELD_SIMULATION_NOT_LEAF_LESION_SEVERITY'
    stats = {'simulated_rows_read': len(data), 'valid_inspection_rows': len(observed),
             'diseases': sorted(observed['Disease_Name'].unique().tolist()),
             'unique_blocks': int(observed['Block_ID'].nunique()),
             'missing_or_uninspected_rows': int(len(data) - len(observed))}
    return grouped, stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--component-root', type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.component_root.resolve()
    daily_path = root / 'data/processed/climate_daily_features.csv'
    synthetic_path = root / 'data/synthetic/synthetic_block_records_multidisease.csv'
    step20_quality = root / 'outputs/reports/step20_nasa_climate_quality.json'
    if not daily_path.is_file():
        raise FileNotFoundError(f'Step20 daily features missing: {daily_path}')
    if not step20_quality.is_file():
        raise FileNotFoundError(f'Step20 source provenance report missing: {step20_quality}')
    src = json.loads(step20_quality.read_text(encoding='utf-8'))
    daily = clean_daily(daily_path)
    context, monthly, q = build_climate_context(daily)
    incidence, stats = build_incidence_summary(synthetic_path)
    out_dir = root / 'outputs/dashboard/climate'
    reports = root / 'outputs/reports'
    processed = root / 'data/processed'
    for folder in [out_dir, reports, processed]: folder.mkdir(parents=True, exist_ok=True)
    p_context = processed / 'climate_daily_context.csv'
    p_month = out_dir / 'climate_monthly_summary.csv'
    p_incidence = out_dir / 'synthetic_observation_incidence_monthly.csv'
    p_threshold = processed / 'climate_historical_reference_p90.json'
    p_summary = out_dir / 'climate_and_incidence_metadata.json'
    p_report = reports / 'step34_m03_climate_incidence_audit.json'
    context['Date'] = context.Date.dt.strftime('%Y-%m-%d')
    context.to_csv(p_context, index=False)
    monthly.to_csv(p_month, index=False)
    incidence.to_csv(p_incidence, index=False)
    p_threshold.write_text(json.dumps({'reference_period':'2011-01-01 to 2022-12-31', 'reference_type':'month-specific empirical p90', 'monthly_p90':q},indent=2),encoding='utf-8')
    metadata = {
        'step':34, 'status':'HISTORICAL_CONTEXT_AND_SYNTHETIC_INCIDENCE_ONLY',
        'climate_days':len(daily), 'monthly_periods':len(monthly),
        'climate_period':{'start':str(daily.Date.min().date()), 'end':str(daily.Date.max().date())},
        'nasa_point':{'latitude':src.get('latitude'), 'longitude':src.get('longitude')},
        'estate_location_verified':False,
        'observation_summary':stats,
        'incidence_definition':'100 * simulated symptomatic bushes / simulated inspected bushes; NOT lesion area severity',
        'climate_context_definition':'Number of NASA weather values above 2011–2022 calendar-month p90; NOT learned disease-risk score',
        'forecast_ready':False, 'image_severity_model_available':False,
        'limitations':[
            'NASA POWER point location NOT verified to match target tea estate.',
            'Synthetic officer observations NOT ground truth or agricultural field validation.',
            'No disease-specific climate-risk model trained by this step.',
            'Sample incidence is NOT image disease lesion-area severity.',
            'Historical context uses same-day measurements known end-of-day; DO NOT feed them to start-of-day forecast origins.',
            'Rainfall / humidity high flags are descriptive, not causal disease impact evidence.'
        ],
        'artifacts':{'daily_climate_context':str(p_context.relative_to(root)),
                     'monthly_climate':str(p_month.relative_to(root)),
                     'synthetic_incidence':str(p_incidence.relative_to(root)),
                     'reference_thresholds':str(p_threshold.relative_to(root))}
    }
    p_summary.write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    p_report.write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    print('='*75)
    print('STEP 34 - CLIMATE CONTEXT + SYNTHETIC INCIDENCE | NOT DISEASE RISK')
    print('='*75)
    print(f'NASA climate days: {len(daily)} | monthly periods: {len(monthly)}')
    print(f'Multi-disease synthetic records: {stats["simulated_rows_read"]} | valid simulated inspections: {stats["valid_inspection_rows"]}')
    print(f'Diseases={stats["diseases"]} | blocks={stats["unique_blocks"]}')
    print(f'NASA point: {src.get("latitude")}, {src.get("longitude")} | ESTATE LOCATION UNVERIFIED')
    print(f'Monthly climate: {p_month}\nSynthetic incidence: {p_incidence}')
    print(f'Dashboard metadata: {p_summary}\nReport: {p_report}')
    print('PASS: historical climate context and simulated incidence dashboard records prepared.')
    print('NOT a climate disease-risk ML model. NOT leaf lesion-area severity.')

if __name__=='__main__':
    main()
