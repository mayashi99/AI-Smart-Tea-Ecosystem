#!/usr/bin/env python3
"""Step 38 climate-only simulated day-7 risk inference.

Inputs: observed NASA weather through origin end-of-day; date/disease only.
The single-point weather is SHARED across all 16 simulated blocks: this is NOT
an officer-observation-conditioned or Nuwara-Eliya-verified estate forecast.
"""
from __future__ import annotations
import argparse
import json
from datetime import date as Date, timedelta
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

DEFAULT_ROOT = Path(__file__).resolve().parents[2]
MODEL_REL = Path('models/climate/step38/climate_risk_models.joblib')
CLIMATE_REL = Path('data/processed/climate_daily_features.csv')
DISEASES = ('Brown Blight', 'Grey Leaf', 'Red Rust', 'Red Spider Mite')
ONEHOT = ('Disease_brown_blight', 'Disease_grey_leaf', 'Disease_red_rust', 'Disease_red_spider_mite')
TARGETS = ('Target_Disease_Active_Day_7', 'Target_New_Onset_By_Day_7')


def risk_band(value: float) -> str:
    """Descriptive demonstration bins, NOT validated agronomic thresholds."""
    return ('LOW' if value < .25 else
            'MODERATE' if value < .50 else
            'HIGH' if value < .75 else 'VERY_HIGH')


def _model_scores(bundle: dict, features_df: pd.DataFrame) -> dict[str, np.ndarray]:
    missing = set(bundle['features']).difference(features_df.columns)
    if missing:
        raise ValueError(f'Missing saved-model features: {sorted(missing)}')
    x = features_df.loc[:, bundle['features']].astype(float).to_numpy()
    if not np.isfinite(x).all():
        raise ValueError('Missing or invalid daily NASA climate features; origin must have historical lookback')
    out = {}
    for target in TARGETS:
        cfg = bundle['selected'][target]
        if cfg['name'] == 'TRAIN_DISEASE_BASELINE':
            probabilities = features_df['Disease_Name'].map(bundle['train_disease_rates'][target]).to_numpy(dtype=float)
            if not np.isfinite(probabilities).all():
                raise ValueError('Unknown disease for training baseline')
        else:
            model_key = f"{target}::{cfg['name']}"
            model = bundle['models'].get(model_key)
            if model is None:
                raise ValueError(f'Model missing: {model_key}')
            probabilities = np.asarray(model.predict(x), dtype=float)
        out[target] = np.clip(probabilities, 0., 1.)
    return out


def load_bundle(component_root: Path) -> dict:
    path = component_root / MODEL_REL
    if not path.is_file():
        raise FileNotFoundError(f'Train Step 38 first: {path}')
    # Joblib/pickle is only safe for files from your trusted local development.
    bundle = joblib.load(path)
    if bundle.get('schema') != 'step38-climate-risk-v1' or set(bundle.get('selected', {})) != set(TARGETS):
        raise ValueError('Unrecognized Step 38 model bundle')
    return bundle


def predict_climate_background(component_root: Path, origin: str, bundle: dict | None = None) -> list[dict]:
    """Return the 4 disease-wide simulated climate scores for one observed date."""
    root = Path(component_root).resolve()
    bundle = bundle or load_bundle(root)
    try:
        origin_date = Date.fromisoformat(origin)
    except ValueError as exc:
        raise ValueError('Origin must be YYYY-MM-DD') from exc
    weather_file = root / CLIMATE_REL
    if not weather_file.is_file():
        raise FileNotFoundError(f'Run Step 20 first: {weather_file}')
    climate = pd.read_csv(weather_file, usecols=['Date', *bundle['climate_features']])
    climate['Date'] = pd.to_datetime(climate['Date'], errors='raise')
    if climate['Date'].duplicated().any():
        raise ValueError('Duplicate climate dates')
    hit = climate.loc[climate['Date'].eq(pd.Timestamp(origin_date))]
    if len(hit) != 1:
        raise ValueError(f'Climate values unavailable for requested date {origin} (no future weather guesses)')
    item = hit.iloc[0]
    seasonal = {
        'Day_Of_Year_Sin': np.sin(2 * np.pi * origin_date.timetuple().tm_yday / 365.25),
        'Day_Of_Year_Cos': np.cos(2 * np.pi * origin_date.timetuple().tm_yday / 365.25),
    }
    frames = []
    for disease in DISEASES:
        record = {'Disease_Name': disease, **{k: float(item[k]) for k in bundle['climate_features']}, **seasonal}
        record.update({k: int(disease == d) for d, k in zip(DISEASES, ONEHOT)})
        frames.append(record)
    features = pd.DataFrame(frames)
    scores = _model_scores(bundle, features)
    results = []
    for index, disease in enumerate(DISEASES):
        a = float(scores[TARGETS[0]][index]); b = float(scores[TARGETS[1]][index])
        results.append({
            'Forecast_Origin_Date': origin,
            'Forecast_Target_Date': str(origin_date + timedelta(days=7)),
            'Disease_Name': disease,
            'Day7_Activity_Score': round(a, 6),
            'Day7_New_Onset_Score': round(b, 6),
            'Activity_Descriptive_Band': risk_band(a),
            'New_Onset_Descriptive_Band': risk_band(b),
            'Activity_Model': bundle['selected'][TARGETS[0]]['name'],
            'New_Onset_Model': bundle['selected'][TARGETS[1]]['name'],
            'Shared_Across_All_16_Simulated_Blocks': True,
            'Synthetic_Model': True,
            'Climate_Point_Verified_For_Target_Estate': False,
            'Observed_Climate_As_Of_End_Of_Day': True,
            'Warning': 'Simulation only. Shared single-point NASA climate, not Nuwara Eliya estate validation; no observed future weather.'
        })
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--component-root', default=str(DEFAULT_ROOT), type=Path)
    parser.add_argument('--date', default='2025-12-24')
    args = parser.parse_args()
    results = predict_climate_background(args.component_root, args.date)
    print(json.dumps(results, indent=2))
    print('PASS: Step38 local model inference; climate shared across all blocks, not live officer-conditioned.')


if __name__ == '__main__':
    main()
