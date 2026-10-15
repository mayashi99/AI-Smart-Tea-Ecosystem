#!/usr/bin/env python3
"""Step40 service smoke test: all 16 blocks and 4 diseases in read-only demo."""
from __future__ import annotations
import argparse
from pathlib import Path
from m03_dashboard_service import (BLOCKS, DISEASES, get_block_dashboard,
                                   get_climate_history, get_overview)
DEFAULT_ROOT=Path(__file__).resolve().parents[2]


def verify(root):
    ov=get_overview(root)
    assert ov['summary']['block_disease_rows']==64
    assert ov['summary']['seven_day_spread_rows']==448
    assert ov['metadata']['field_validated'] is False
    assert ov['metadata']['dynamic_observation_reforecast_available'] is False
    for block in BLOCKS:
        all_diseases=get_block_dashboard(root,block)
        assert len(all_diseases['block_disease_context'])==4
        assert len(all_diseases['seven_day_spread_forecasts'])==28
        for disease in DISEASES:
            result=get_block_dashboard(root,block,disease)
            assert len(result['block_disease_context'])==1
            assert len(result['seven_day_spread_forecasts'])==7
            assert [r['horizon_day'] for r in result['seven_day_spread_forecasts']]==list(range(1,8))
            assert result['is_live'] is False
            assert result['block_disease_context'][0]['leaf_lesion_area_pct'] is None
    climate=get_climate_history(root,12)
    assert len(climate['monthly_records'])==12
    assert all(r['Year_Month']<'2025-12' for r in climate['monthly_records'])
    for val in ['B00','B17','foo']:
        try:get_block_dashboard(root,val)
        except ValueError:pass
        else:raise AssertionError(f'Invalid block accepted: {val}')
    try:get_block_dashboard(root,'B16','Healthy')
    except ValueError:pass
    else:raise AssertionError('Healthy incorrectly accepted as spread disease.')
    print('STEP40 VERIFY - PASS')
    print('64/64 block-disease lookups and 16 all-disease block lookups tested.')
    print('All 7 forecast horizons per disease; no invented lesion severity.')
    print('Climate monthly history is strictly before 2025-12; bad inputs rejected.')
    print('NOTE: READ-ONLY HISTORICAL SIMULATION, not live officer-conditioned inference.')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--component-root',type=Path,default=DEFAULT_ROOT)
    verify(ap.parse_args().component_root)

if __name__=='__main__': main()
