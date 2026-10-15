"""Check generated officer-report / block forecast CSVs; standard-library only."""
import csv
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data' / 'synthetic'


def read(name):
    with (OUT / name).open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def validate():
    blocks = read('estate_blocks.csv')
    edges = read('block_adjacency.csv')
    reports = read('officer_disease_observations.csv')
    data = read('synthetic_block_records.csv')
    assert len(blocks) == 16, 'Expected 16 blocks'
    assert len(edges) == 48, 'Expected 48 directed 4-neighbor edges'
    assert len(data) == 21072, 'Expected 16 x 1317 block-days'
    keys = [(r['Date'], r['Block_ID']) for r in data]
    assert len(keys) == len(set(keys)), 'Duplicate block-day found'
    assert len(reports) == len({r['Observation_ID'] for r in reports})
    block_set = {b['Block_ID'] for b in blocks}
    assert block_set == {r['Block_ID'] for r in data}
    assert all(e['Source_Block'] in block_set and e['Target_Block'] in block_set for e in edges)
    positive = Counter(); targets = Counter(); splits = Counter()
    for r in data:
        origin = date.fromisoformat(r['Date'])
        splits[r['Split']] += 1
        assert r['Forecast_Origin_Date'] == r['Date']
        assert r['Observation_Source'] == 'SYNTHETIC_FIELD_SIMULATION'
        assert r['Climate_Source'] == 'NASA_POWER_SINGLE_POINT'
        assert r['All_7_Targets_Available'] == str(int(origin + timedelta(days=7) <= date(2026,8,9)))
        has_obs = r['Observation_Available'] == '1'
        if has_obs:
            n = int(r['Inspected_Bushes'])
            k = int(r['Symptomatic_Bushes'])
            assert 0 <= k <= n and n > 0
            assert abs(float(r['Sample_Incidence_Pct']) - round(k/n*100, 2)) < .011
        else:
            assert not r['Inspected_Bushes'] and not r['Symptomatic_Bushes'] and not r['Sample_Incidence_Pct']
        for h in range(1, 8):
            assert date.fromisoformat(r[f'Target_Date_Day_{h}']) == origin + timedelta(days=h)
            tgt = r[f'Target_Disease_Active_Day_{h}']
            if origin + timedelta(days=h) <= date(2026,8,9):
                assert tgt in ('0','1')
                targets[h] += 1
                positive[h] += int(tgt)
            else:
                assert tgt == ''
        if r['Split'] == 'train':
            assert origin + timedelta(days=7) <= date(2024,12,31)
        elif r['Split'] == 'validation':
            assert origin >= date(2025,1,8) and origin+timedelta(days=7) <= date(2025,12,31)
        elif r['Split'] == 'test':
            assert origin >= date(2026,1,8) and origin+timedelta(days=7) <= date(2026,8,9)
    for r in reports:
        assert (r['Date'],r['Block_ID']) in set(keys)
        assert 0 <= int(r['Symptomatic_Bushes']) <= int(r['Inspected_Bushes'])
    assert all(0 < positive[h] < targets[h] for h in range(1,8)), 'Degenerate target label distribution'
    print('PASS: rows', len(data), 'reports', len(reports), 'blocks', len(blocks), 'edges', len(edges))
    print('PASS: split counts', dict(splits))
    print('PASS: positive label prevalence', {h: round(positive[h]/targets[h],3) for h in range(1,8)})
    print('PASS: 7-day date alignment, observation counts, provenance, keys, missing targets and splits')


if __name__ == '__main__':
    validate()
