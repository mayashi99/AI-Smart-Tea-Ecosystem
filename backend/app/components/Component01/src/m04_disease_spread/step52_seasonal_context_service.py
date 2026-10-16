"""Step52: current-calendar seven-day conditional forecast with historical seasonal context.

Only today's submitted field observation is current. The remaining context is the
historical 2025 series shifted into an analogous season. Weather and other-block
observations are NOT presented as measured currently. Uses trusted train-fitted
preprocessors and Step31 model selection; no retraining or fake predictions.

This is a prototype conditional estimate, NOT validated live plantation forecasting.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import os
import tempfile
import uuid

import pandas as pd

from dynamic_spread_service import (
    ROOT, BLOCKS, DISEASES, SOURCE_COLS, CSV_FIELDS, _LOCK,
    validate_observation, prepare_24h_inputs, arrays_for_disease,
)

SLT = timezone(timedelta(hours=5, minutes=30))
HISTORY_FILE = 'data/synthetic/synthetic_block_records_multidisease.csv'
BLOCK_META_FILE = 'data/synthetic/estate_blocks.csv'
ADJACENCY_FILE = 'data/synthetic/block_adjacency.csv'
OBSERVATIONS_FILE = 'data/runtime/step52_officer_observations.csv'
LATEST_FILE = 'outputs/dashboard/dynamic/step52_latest_seasonal_forecast.json'
SCHEMA = 'step52-seasonal-context-v1'
EXPECTED_ROWS = 21 * len(BLOCKS) * len(DISEASES)

class SeasonalContextUnavailable(Exception):
    """Required existing historical data, fitted pipeline or models unavailable."""


def sri_lanka_today() -> date:
    return datetime.now(SLT).date()


def _require(ok, message):
    if not ok:
        raise SeasonalContextUnavailable(message)


def _candidate_2025(today: date) -> date:
    # Feb-29 has no match in 2025. Choose the closest annual calendar day.
    day = min(today.day, 28) if today.month == 2 else today.day
    target = date(2025, today.month, day)
    return min(max(target, date(2025, 1, 21)), date(2025, 12, 24))


def _source_and_reference(root: Path, today: date):
    """Find nearest available, complete historical 21-day context within 2025.

    Only allowed source rows are historical observations. No future target columns.
    This function is read-only; future-day values are NOT read for inference.
    """
    source = root / HISTORY_FILE
    for required in [source, root / BLOCK_META_FILE, root / ADJACENCY_FILE]:
        _require(required.is_file(), f'Forecast prerequisite missing: {required.relative_to(root)}')
    try:
        raw = pd.read_csv(source, usecols=SOURCE_COLS, encoding='utf-8-sig', low_memory=False)
        raw['Date'] = pd.to_datetime(raw['Date'], errors='raise')
    except (ValueError, KeyError, OSError, pd.errors.ParserError) as exc:
        raise SeasonalContextUnavailable(f'Historical source cannot be read: {type(exc).__name__}') from exc
    _require(not raw.duplicated(['Date', 'Disease_Name', 'Block_ID']).any(), 'Duplicate historical keys')
    _require(set(BLOCKS).issubset(set(raw.Block_ID)) and set(DISEASES).issubset(set(raw.Disease_Name)),
             'Historical 16-block / 4-disease contract missing')
    _require(raw['Estate_ID'].nunique() == 1, 'Historical estate ID mismatch')

    raw = raw.loc[(raw.Date >= pd.Timestamp('2025-01-01')) &
                  (raw.Date <= pd.Timestamp('2025-12-24'))].copy()
    _require(not raw.empty, 'No 2025 historical context records')
    # No assumptions about which 2025 days are complete: inspect availability.
    group_sizes = raw.groupby('Date', observed=True).size()
    full_days = set(group_sizes.index[group_sizes.eq(len(BLOCKS) * len(DISEASES))].date)
    valid_endings = [end for end in sorted(full_days)
                     if date(2025, 1, 21) <= end <= date(2025, 12, 24)
                     and all(end - timedelta(days=i) in full_days for i in range(21))]
    _require(bool(valid_endings), 'No complete 21-day historical 2025 context window')
    desired = _candidate_2025(today)
    analogue_end = min(valid_endings, key=lambda day: (abs((day-desired).days), day))
    start = analogue_end - timedelta(days=20)
    window = raw.loc[(raw.Date >= pd.Timestamp(start)) & (raw.Date <= pd.Timestamp(analogue_end))].copy()
    _require(len(window) == EXPECTED_ROWS and window.Estate_ID.nunique() == 1,
             'Historical context dimensions incorrect')
    # Transform calendar position for actual current date. Note provenance below.
    window['Date'] = window['Date'] + pd.Timedelta(days=(today - analogue_end).days)
    _require(window['Date'].max().date() == today,
             'Current calendar-date alignment failed')
    return window, analogue_end


def _atomic_csv(path: Path, df: pd.DataFrame):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp = tempfile.mkstemp(prefix='step52_', suffix='.csv', dir=path.parent)
    os.close(handle)
    try:
        df.to_csv(tmp, index=False)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _atomic_json(path: Path, record: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp = tempfile.mkstemp(prefix='step52_', suffix='.json', dir=path.parent)
    os.close(handle)
    try:
        Path(tmp).write_text(json.dumps(record, indent=2, allow_nan=False), encoding='utf-8')
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _previous_today(root: Path, today: date):
    path = root / OBSERVATIONS_FILE
    if not path.exists():
        return []
    try:
        records = pd.read_csv(path, encoding='utf-8-sig', keep_default_na=False)
        _require(list(records.columns) == CSV_FIELDS, 'Step52 observation CSV schema mismatch')
        output = []
        for record in records.to_dict('records'):
            if str(record['forecast_origin_date']) != today.isoformat():
                continue
            output.append(validate_observation(record['block_id'], record['disease_name'],
                int(record['inspected_bushes']), int(record['symptomatic_bushes'])))
        return output
    except (OSError, ValueError, KeyError, pd.errors.ParserError) as exc:
        raise SeasonalContextUnavailable(f'Saved officer records cannot be read: {exc}') from exc


def seasonal_status(root=ROOT, *, today=None):
    root = Path(root).resolve()
    today = today or sri_lanka_today()
    output = {
        'date': today.isoformat(),
        'forecast_origin_date': today.isoformat(),
        'forecast_target_start': (today+timedelta(days=1)).isoformat(),
        'forecast_target_end': (today+timedelta(days=7)).isoformat(),
        'required_recent_daily_records': False,
        'forecast_method': 'HISTORICAL_SEASONAL_CONTEXT_WITH_TODAY_OFFICER_OBSERVATION',
        'field_validation_completed': False,
        'ready': False,
    }
    try:
        _, reference_date = _source_and_reference(root, today)
        output['historical_reference_origin'] = reference_date.isoformat()
        output['ready'] = True
    except SeasonalContextUnavailable as exc:
        output['reason'] = str(exc)
    return output


def seasonal_predict(root, block_id, disease_name, inspected_bushes, symptomatic_bushes,
                     *, save=False, predictor=None, today=None):
    """Run real saved models with 21-day historical proxy + current inspection.

    IMPORTANT: The forecast's current-day calendar labels are actual dates, while
    unobserved block/climate context is historical, not live. Do not claim
    contemporary climate readings, validated risk thresholds or transmission paths.
    """
    root = Path(root).resolve()
    today = today or sri_lanka_today()
    obs = validate_observation(block_id, disease_name, inspected_bushes, symptomatic_bushes)
    with _LOCK:
        shifted, analog_date = _source_and_reference(root, today)
        existing = _previous_today(root, today)
        # Keep all preprocessing faithful to Step25/26's train-fitted pipeline.
        # Use an isolated temporary source file; never overwrite historical CSV.
        with TemporaryDirectory(prefix='tea_step52_') as temporary:
            context_file = Path(temporary) / 'dated_historical_context.csv'
            shifted.to_csv(context_file, index=False)
            try:
                built = prepare_24h_inputs(root, today, existing+[obs], source_csv=context_file)
                scaled, tabular = arrays_for_disease(built, disease_name)
                if predictor is None:
                    from selected_spread_inference import SelectedSpreadPredictor
                    predictor = SelectedSpreadPredictor(root, threads=2)
                raw_predictions = predictor.predict_disease(disease_name, scaled, tabular)
            except (ValueError, KeyError, FileNotFoundError, RuntimeError, ImportError, OSError) as exc:
                raise SeasonalContextUnavailable(
                    f'Fitted preprocessor/model inference unavailable: {type(exc).__name__}: {exc}') from exc
        _require(len(raw_predictions) == 16*7, 'Model must return 112 block/day predictions')
        seen=set()
        all_rows=[]
        for raw in raw_predictions:
            row=dict(raw)
            pair=(row.get('block_id'), row.get('horizon_day'))
            _require(row.get('disease_name') == disease_name and row.get('block_id') in BLOCKS and
                     type(row.get('horizon_day')) is int and 1 <= row['horizon_day'] <= 7 and
                     pair not in seen, 'Invalid/duplicate block/day prediction')
            seen.add(pair)
            row.update(forecast_origin_date=today.isoformat(),
                       forecast_target_date=(today+timedelta(days=row['horizon_day'])).isoformat(),
                       data_provenance='HISTORICAL_SEASONAL_CONTEXT_PLUS_OFFICER_OBSERVATION')
            all_rows.append(row)
        selected = [row for row in all_rows if row['block_id'] == block_id]
        _require(len(seen) == 112 and len(selected) == 7, 'Incomplete forecast coverage')
        output = {
            'schema_version': SCHEMA,
            'forecast_method': 'HISTORICAL_SEASONAL_CONTEXT_PLUS_TODAY_FIELD_OBSERVATION',
            'forecast_origin_date': today.isoformat(),
            'forecast_target_start': (today+timedelta(days=1)).isoformat(),
            'forecast_target_end': (today+timedelta(days=7)).isoformat(),
            'historical_reference_origin': analog_date.isoformat(),
            'selected_block_id': block_id,
            'disease_name': disease_name,
            'submitted_observation': obs,
            'history_window_days': 14,
            'model_features': 48,
            'other_blocks_observed_today': False,
            'current_climate_observed': False,
            'field_validated': False,
            'model_trained_on_synthetic_records': True,
            'forecast_uncertainty_calibrated': False,
            'limitations': [
                'Historical seasonal analog provides climate and unobserved block context, not actual current measurements.',
                'Current officer observation is used for the selected block and disease; other current block observations may be missing.',
                'Model was trained on synthetic records and has not been validated on an independent real estate.',
                'Predicted relative block risk is not evidence of disease transmission or treatment efficacy.',
            ],
            'warning': ('Conditional model estimates from historical seasonal patterns and an officer-entered observation. '
                        'Not independently field validated; confirm disease and treatment with an agronomist.'),
            'selected_block_daily_forecast': sorted(selected, key=lambda x: x['horizon_day']),
            'all_block_forecast_for_selected_disease': all_rows,
            'previous_officer_updates_applied': len({(x['block_id'], x['disease_name']) for x in existing}),
            'saved': False,
        }
        if save:
            csv_path = root / OBSERVATIONS_FILE
            df = pd.read_csv(csv_path, encoding='utf-8-sig') if csv_path.exists() else pd.DataFrame(columns=CSV_FIELDS)
            _require(list(df.columns) == CSV_FIELDS, 'Observation storage schema mismatch')
            new_row = {**obs, 'observation_id':uuid.uuid4().hex,
                       'forecast_origin_date':today.isoformat(),
                       'created_at_utc':datetime.now(timezone.utc).isoformat()}
            incoming = pd.DataFrame([new_row], columns=CSV_FIELDS)
            df = (incoming if df.empty else pd.concat([df, incoming], ignore_index=True))[CSV_FIELDS]
            _atomic_csv(csv_path, df)
            output['saved'] = True
            _atomic_json(root / LATEST_FILE, output)
        return output


def seasonal_latest(root=ROOT):
    path = Path(root) / LATEST_FILE
    if not path.is_file():
        raise SeasonalContextUnavailable('No saved forecast yet')
    try:
        result = json.loads(path.read_text(encoding='utf-8'))
        _require(result.get('schema_version') == SCHEMA, 'Unexpected saved forecast schema')
        _require(result.get('forecast_origin_date') == sri_lanka_today().isoformat(),
                 'Saved forecast belongs to a previous date; please generate a new forecast')
        return result
    except (OSError, ValueError, KeyError) as exc:
        raise SeasonalContextUnavailable(f'Saved forecast unavailable: {exc}') from exc


def seasonal_observations(root=ROOT, limit=30):
    path = Path(root) / OBSERVATIONS_FILE
    if not path.is_file():
        return {'count':0, 'records':[]}
    try:
        df = pd.read_csv(path, encoding='utf-8-sig', keep_default_na=False)
        _require(list(df.columns) == CSV_FIELDS, 'Observation CSV schema mismatch')
        return {'count':len(df), 'records':df.tail(limit).iloc[::-1].to_dict('records')}
    except (OSError, ValueError, KeyError) as exc:
        raise SeasonalContextUnavailable(f'Observation history unavailable: {exc}') from exc
