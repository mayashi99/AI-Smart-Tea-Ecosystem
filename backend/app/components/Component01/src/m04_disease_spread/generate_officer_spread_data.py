"""Generate reproducible officer-style SIMULATED red-rust reports and 7-day training targets.

The only real data used are NASA POWER climate measurements at a SINGLE point.
The estate blocks, disease outbreaks, officer inspections, and disease targets are
SIMULATED for prototyping; they are not tea-estate field observations.

Run from any working directory:
python backend/app/components/Component01/src/m04_disease_spread/generate_officer_spread_data.py
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
from collections import Counter, deque
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CLIMATE = ROOT / 'data/raw/climate/nasa_power_daily.csv'
DEFAULT_OUT = ROOT / 'data/synthetic'


def clip(x, low, high):
    return max(low, min(high, x))


def write_csv(path, rows, columns):
    with path.open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


def read_climate(path, start, end):
    if not path.exists():
        raise FileNotFoundError(f'Missing NASA POWER input CSV: {path}')
    with path.open(encoding='utf-8-sig') as f:
        lines = f.readlines()
    pos = next((i for i, ln in enumerate(lines) if ln.strip().startswith('YEAR,MO,DY,')), None)
    if pos is None:
        raise ValueError('NASA POWER CSV header YEAR,MO,DY not found')
    reader = csv.DictReader(lines[pos:])
    cols = ('T2M', 'RH2M', 'PRECTOTCORR', 'ALLSKY_SFC_SW_DWN')
    if not set(cols).issubset(reader.fieldnames or []):
        raise ValueError('Climate variables missing')
    out = []
    for r in reader:
        day = date(int(r['YEAR']), int(r['MO']), int(r['DY']))
        if day < start or day > end:
            continue
        values = {k: float(r[k]) for k in cols}
        if any(v == -999 or not math.isfinite(v) for v in values.values()):
            raise ValueError(f'Invalid climate data for {day}')
        out.append({'Date': day, **values})
    out.sort(key=lambda r: r['Date'])
    expected = (end - start).days + 1
    if len(out) != expected or len({r['Date'] for r in out}) != expected:
        raise ValueError(f'Missing or duplicate date(s): wanted {expected}; found {len(out)}')
    return out


def make_grid(side, rng):
    blocks, neighbors = [], {}
    for r in range(side):
        for c in range(side):
            bid = f'B{r * side + c + 1:02d}'
            blocks.append({'Block_ID': bid, 'Block_Name': f'Demo Block {bid}',
                           'Grid_Row': r + 1, 'Grid_Column': c + 1,
                           'Relative_Vulnerability': round(rng.uniform(.85, 1.18), 3),
                           'Estate_ID': 'DEMO_ESTATE_01', 'Block_Source': 'DUMMY_GRID'})
    for block in blocks:
        b = block['Block_ID']
        r, c = block['Grid_Row'], block['Grid_Column']
        neighbors[b] = [x['Block_ID'] for x in blocks
                        if abs(x['Grid_Row'] - r) + abs(x['Grid_Column'] - c) == 1]
    return blocks, neighbors


def binomial(n, p, rng):
    return sum(rng.random() < p for _ in range(n))


def split_for_origin(day, start, end):
    """Seven-day targets must remain wholly inside the assigned partition."""
    if day < start + timedelta(days=14):
        return 'warmup'
    if day.year == 2023:
        return 'train' if day + timedelta(days=7) <= date(2024, 12, 31) else 'gap'
    if day.year == 2024:
        return 'train' if day + timedelta(days=7) <= date(2024, 12, 31) else 'gap'
    if day.year == 2025:
        return 'validation' if day >= date(2025, 1, 8) and day + timedelta(days=7) <= date(2025, 12, 31) else 'gap'
    if day.year == 2026:
        return 'test' if day >= date(2026, 1, 8) and day + timedelta(days=7) <= end else 'inference_only'
    return 'gap'


def generate(climate_path, out_dir, start, end, seed=20261013, side=4, horizon=7):
    if horizon != 7:
        raise ValueError('This component requires seven separate forecast days (horizon=7)')
    if side < 2 or side > 7:
        raise ValueError('Grid side must be between 2 and 7')
    weather = read_climate(climate_path, start, end)
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    blocks, neighbors = make_grid(side, rng)
    ids = [b['Block_ID'] for b in blocks]
    vulnerability = {b['Block_ID']: b['Relative_Vulnerability'] for b in blocks}
    active = {b: 1 if b in ('B06', 'B11') else 0 for b in ids}
    infection_age = {b: 1 if active[b] else 0 for b in ids}
    prev_incidence = {b: 0.0 for b in ids}
    since_inspection = {b: 365 for b in ids}
    humid_history, rain_history = deque(maxlen=7), deque(maxlen=7)
    records = {b: [] for b in ids}
    reports = []

    for obs in weather:
        day = obs['Date']
        temp, rh, rain, solar = (obs[k] for k in
                                 ('T2M', 'RH2M', 'PRECTOTCORR', 'ALLSKY_SFC_SW_DWN'))
        humid_history.append(rh)
        rain_history.append(rain)
        humid7 = sum(humid_history) / len(humid_history)
        rain7 = sum(rain_history)
        pressure = clip(0.42 + 0.021 * (humid7 - 80) + 0.0027 * (rain7 - 40)
                        - 0.026 * max(temp - 29, 0) - 0.012 * max(solar - 6, 0), 0.05, 0.95)
        prior = active.copy()
        updated, next_age = {}, {}
        for b in ids:
            neighbor_fraction = sum(prior[n] for n in neighbors[b]) / len(neighbors[b])
            if prior[b]:
                recovery = 0.0 if infection_age[b] < 4 else 0.06 + 0.04 * (1 - pressure)
                updated[b] = int(rng.random() >= recovery)
                next_age[b] = infection_age[b] + 1 if updated[b] else 0
            else:
                new_prob = clip((0.0009 + 0.015 * pressure + 0.052 * neighbor_fraction)
                                * vulnerability[b], .0001, .14)
                updated[b] = int(rng.random() < new_prob)
                next_age[b] = 1 if updated[b] else 0
        active, infection_age = updated, next_age

        daily = {}
        for b in ids:
            # Simulated disease pressure controls how many bushes show symptoms.
            latent_prevalence = (clip(.075 + .012 * min(infection_age[b], 27)
                                     + rng.uniform(-.022, .045), .035, .55) if active[b] else 0.0)
            inspected = rng.random() < 0.67
            count = rng.randint(20, 45) if inspected else None
            symptomatic = binomial(count, latent_prevalence, rng) if inspected else None
            observed_pct = round(100 * symptomatic / count, 2) if inspected else None
            if inspected:
                prev_incidence[b] = observed_pct
                since_inspection[b] = 0
                reports.append({
                    'Observation_ID': f'SIM-{day:%Y%m%d}-{b}',
                    'Date': day.isoformat(), 'Block_ID': b,
                    'Disease_Name': 'Red Rust' if symptomatic > 0 else 'No symptoms observed',
                    'Image_Filename': '',  # Never pretend an image exists.
                    'Inspected_Bushes': count, 'Symptomatic_Bushes': symptomatic,
                    'Sample_Incidence_Pct': observed_pct,
                    'Officer_Confirmed': 'SIMULATED',
                    'Observation_Source': 'SYNTHETIC_FIELD_SIMULATION',
                })
            else:
                since_inspection[b] += 1
            daily[b] = {
                'Date': day.isoformat(), 'Estate_ID': 'DEMO_ESTATE_01', 'Block_ID': b,
                'Disease_Name': 'Red Rust',
                'Observation_Available': int(inspected),
                'Inspected_Bushes': count if inspected else '',
                'Symptomatic_Bushes': symptomatic if inspected else '',
                'Sample_Incidence_Pct': observed_pct if inspected else '',
                'Latest_Observed_Incidence_Pct': prev_incidence[b],
                'Days_Since_Last_Inspection': since_inspection[b],
                'T2M': temp, 'RH2M': rh, 'PRECTOTCORR': rain,
                'ALLSKY_SFC_SW_DWN': solar,
                'Humidity_Mean_7D': round(humid7, 3),
                'Rainfall_Sum_7D': round(rain7, 3),
                'Climate_Source': 'NASA_POWER_SINGLE_POINT',
                'Observation_Source': 'SYNTHETIC_FIELD_SIMULATION',
                '_latent_active': active[b],
                '_latent_incidence': round(latent_prevalence * 100, 2),
                '_new_onset_today': int(prior[b] == 0 and active[b] == 1),
            }
        for b in ids:
            neighbors_b = neighbors[b]
            daily[b]['Neighbor_Latest_Incidence_Mean_Pct'] = round(
                sum(prev_incidence[n] for n in neighbors_b) / len(neighbors_b), 2)
            daily[b]['Neighbor_Recent_Positive_Count'] = sum(prev_incidence[n] > 0 for n in neighbors_b)
            records[b].append(daily[b])

    main_rows = []
    for b in ids:
        by_date = records[b]
        for i, row in enumerate(by_date):
            r = {k: v for k, v in row.items() if not k.startswith('_')}
            r['Forecast_Origin_Date'] = row['Date']
            r['Forecast_Horizon_Days'] = 7
            all_targets_available = i + 7 < len(by_date)
            r['All_7_Targets_Available'] = int(all_targets_available)
            # All labels are SYNTHETIC. They are NOT available to inference as predictors.
            for h in range(1, 8):
                r[f'Target_Date_Day_{h}'] = (date.fromisoformat(row['Date']) + timedelta(days=h)).isoformat()
                if i + h < len(by_date):
                    future = by_date[i+h]
                    r[f'Target_Disease_Active_Day_{h}'] = future['_latent_active']
                    r[f'Target_Incidence_Pct_Day_{h}'] = future['_latent_incidence']
                    r[f'Target_New_Onset_By_Day_{h}'] = int(
                        row['_latent_active'] == 0 and any(
                            by_date[j]['_new_onset_today'] == 1 for j in range(i+1, i+h+1)))
                else:
                    r[f'Target_Disease_Active_Day_{h}'] = ''
                    r[f'Target_Incidence_Pct_Day_{h}'] = ''
                    r[f'Target_New_Onset_By_Day_{h}'] = ''
            r['Split'] = split_for_origin(date.fromisoformat(row['Date']), start, end)
            main_rows.append(r)
    main_rows.sort(key=lambda r: (r['Date'], r['Block_ID']))
    adj_rows = [{'Source_Block': b, 'Target_Block': n, 'Relationship': 'DUMMY_FOUR_NEIGHBOR'}
                for b in ids for n in sorted(neighbors[b])]
    write_csv(out_dir / 'estate_blocks.csv', blocks, list(blocks[0]))
    write_csv(out_dir / 'block_adjacency.csv', adj_rows, list(adj_rows[0]))
    write_csv(out_dir / 'officer_disease_observations.csv', reports, list(reports[0]))
    write_csv(out_dir / 'synthetic_block_records.csv', main_rows, list(main_rows[0]))
    (out_dir / 'block_layout.json').write_text(json.dumps([
        {'Block_ID': b['Block_ID'], 'Grid_Row': b['Grid_Row'],
         'Grid_Column': b['Grid_Column'], 'Neighbors': neighbors[b['Block_ID']]}
        for b in blocks], indent=2), encoding='utf-8')
    splits = dict(sorted(Counter(row['Split'] for row in main_rows).items()))
    provenance = {
        'Data_Kind': 'SYNTHETIC_DISEASE_HISTORY_REAL_CLIMATE',
        'Disease': 'Red Rust only (other five image classes NOT modelled for spread)',
        'Seed': seed, 'Estate': 'DEMO_ESTATE_01', 'Grid_Size': f'{side}x{side}',
        'Block_Count': len(ids), 'First_Date': start.isoformat(), 'Last_Date': end.isoformat(),
        'Historical_Climate_Source': 'NASA POWER (6.7789N,79.9301E), ONE shared geographic point',
        'Historical_Climate_Provenance': 'REAL_NASA_POWER',
        'All_Blocks_And_Disease_History': 'SIMULATED_NOT_FIELD_OBSERVED',
        'Reports': len(reports), 'Daily_Block_Records': len(main_rows),
        'Target_Horizon_Days': 7, 'Targets': [f'Target_Disease_Active_Day_{i}' for i in range(1,8)],
        'Feature_Rule': 'Use only current/past observations and climate. Never train with any Target_* as features.',
        'Splits': splits,
        'Important_Caveats': [
            'Do NOT present simulation metrics as real-estate forecasting accuracy.',
            'One photo cannot measure whole-block infection; sampled bushes create the observation incidence.',
            'No actual leaf image files are supplied by the generated observation CSV.',
            'Climate ends on 2026-08-09; a forecast for December 2026 requires later inputs or an explicitly simulated scenario.',
            'The same single NASA climate point is applied to every dummy block.',
        ],
    }
    (out_dir / 'provenance.json').write_text(json.dumps(provenance, indent=2), encoding='utf-8')
    return provenance


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--climate', type=Path, default=DEFAULT_CLIMATE)
    p.add_argument('--output', type=Path, default=DEFAULT_OUT)
    p.add_argument('--start', type=date.fromisoformat, default=date(2023, 1, 1))
    p.add_argument('--end', type=date.fromisoformat, default=date(2026, 8, 9))
    p.add_argument('--seed', type=int, default=20261013)
    p.add_argument('--grid-side', type=int, default=4)
    args = p.parse_args()
    result = generate(args.climate, args.output, args.start, args.end, args.seed, args.grid_side)
    print(json.dumps(result, indent=2))
