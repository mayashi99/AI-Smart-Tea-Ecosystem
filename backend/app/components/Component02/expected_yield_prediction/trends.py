"""Monthly yield trends; future inputs use seasonal historical climate means."""
from pathlib import Path

import pandas as pd

from .catboost.catboost_predict import FEATURES, load_model

DATA_PATH = Path(__file__).parent / 'data' / 'raw' / 'expected yield.csv'
CLIMATE = ['Temperature', 'Rainfall_mm', 'Humidity', 'Wind_Speed', 'Solar_Radiation']
GROWN_TYPES = ('HIGH grown', 'MID grown', 'LOW grown')


def monthly_values(frame, column):
    # Sum weekly kg/acre for each location, then average locations equally.
    totals = frame.groupby(['Year', 'Month_Number', 'Location'])[column].sum(min_count=1)
    return totals.groupby(level=['Year', 'Month_Number']).mean()


def build_trends(grown_type, horizon=12):
    if grown_type not in GROWN_TYPES:
        raise ValueError('Choose HIGH grown, MID grown, or LOW grown.')
    data = pd.read_csv(DATA_PATH)
    data = data[data.Grown_Type == grown_type].copy()
    if data.empty:
        raise ValueError('No historical data is available for this grown type.')
    model = load_model()
    actual = monthly_values(data, 'kg_per_Acre')
    test = data[data.Year == 2025].copy()
    predicted = pd.Series(dtype=float)
    if not test.empty:
        test['prediction'] = model.predict(test[FEATURES])
        predicted = monthly_values(test, 'prediction')
    last_year, last_month = actual.index.max()
    last_period = pd.Period(year=int(last_year), month=int(last_month), freq='M')
    seasonal = data.groupby(['Month_Number', 'Week_Number', 'Location', 'Grown_Type'], as_index=False)[CLIMATE].mean()
    future_frames = []
    for offset in range(1, horizon + 1):
        period = last_period + offset
        inputs = seasonal[seasonal.Month_Number == period.month].copy()
        if inputs.empty:
            raise ValueError('Seasonal climate data is missing for a forecast month.')
        inputs['Year'] = period.year
        future_frames.append(inputs)
    future = pd.concat(future_frames, ignore_index=True)
    future['prediction'] = model.predict(future[FEATURES])
    forecast = monthly_values(future, 'prediction')
    points = []
    for (year, month), value in actual.items():
        test_value = predicted.get((year, month))
        points.append({'date': f'{year:04d}-{month:02d}', 'actual': round(float(value), 2),
                       'test_prediction': round(float(test_value), 2) if pd.notna(test_value) else None,
                       'forecast': None})
    for (year, month), value in forecast.items():
        points.append({'date': f'{year:04d}-{month:02d}', 'actual': None,
                       'test_prediction': None, 'forecast': round(float(value), 2)})
    return {'grown_type': grown_type, 'model': 'CatBoost', 'unit': 'kg/acre/month',
            'test_year': 2025, 'forecast_months': horizon,
            'locations': sorted(data.Location.unique().tolist()), 'points': points,
            'methodology': 'Weekly yields are summed per location and month, then averaged equally across locations. Future predictions use historical average climate conditions for each location, month and week; they are seasonal scenarios, not weather forecasts.'}
