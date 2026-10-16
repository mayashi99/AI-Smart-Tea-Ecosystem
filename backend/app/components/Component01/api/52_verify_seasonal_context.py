"""Step52 isolated contract/integration tests (DOES NOT validate estate accuracy).

Test fixture data and stub predictions exist in TemporaryDirectory ONLY and are
never bundled with/used for actual forecasts. Trained-model check is Step46 on
user's real checkpoint after installation.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import sys

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
SRC = HERE.parents[1] / 'src/m04_disease_spread'
sys.path.insert(0, str(SRC))
import step52_seasonal_context_service as s

class InstrumentedPredictor:
    def __init__(self): self.calls=[]
    def predict_disease(self, disease, history, tabular):
        assert history.shape == (14, 16, 48) and tabular.shape == (16, 48)
        self.calls.append(disease)
        return [{
            'disease_name':disease, 'block_id':b, 'horizon_day':day,
            'incidence_percent_prediction':float(day),
            'activity_predicted_class':0, 'new_onset_predicted_class':0,
            'activity_probability_uncalibrated':None,
            'new_onset_probability_uncalibrated':None,
        } for day in range(1, 8) for b in s.BLOCKS]


def make_fixture(root, date_end=date(2025,10,16)):
    source = root/s.HISTORY_FILE
    source.parent.mkdir(parents=True, exist_ok=True)
    rows=[]
    for lag in range(20,-1,-1):
        day = date_end-timedelta(days=lag)
        for b in s.BLOCKS:
            for disease in s.DISEASES:
                rows.append({
                    'Date':day.isoformat(),'Estate_ID':'ESTATE_A',
                    'Block_ID':b,'Disease_Name':disease,
                    'Observation_Available':1,'Inspected_Bushes':100,
                    'Symptomatic_Bushes':10,'Sample_Incidence_Pct':10,
                    'Latest_Observed_Incidence_Pct':10,'Days_Since_Last_Inspection':0,
                    'T2M':25,'RH2M':80,'PRECTOTCORR':1.5,
                    'ALLSKY_SFC_SW_DWN':13,'Humidity_Mean_7D':80,
                    'Rainfall_Sum_7D':10.5,
                    'Neighbor_Latest_Incidence_Mean_Pct':10,
                    'Neighbor_Recent_Positive_Count':1,
                })
    pd.DataFrame(rows,columns=s.SOURCE_COLS).to_csv(source,index=False)
    (root/s.BLOCK_META_FILE).parent.mkdir(parents=True,exist_ok=True)
    (root/s.BLOCK_META_FILE).write_text('Estate_ID,Block_ID,Grid_Row,Grid_Column,Relative_Vulnerability\n')
    (root/s.ADJACENCY_FILE).write_text('Source_Block,Target_Block\n')


def main():
    today = date(2026,10,16)
    with TemporaryDirectory(prefix='step52_verifier_') as name:
        root=Path(name)
        assert s.seasonal_status(root,today=today)['ready'] is False
        make_fixture(root)
        status=s.seasonal_status(root,today=today)
        assert status['ready'] and status['historical_reference_origin']=='2025-10-16'
        assert status['forecast_target_start']=='2026-10-17'
        assert status['forecast_target_end']=='2026-10-23'
        print('PASS: Missing context fails closed; historical same-season dates found')
        past=s._source_and_reference(root,today)[0]
        assert past['Date'].min().date()==date(2026,9,26)
        assert past['Date'].max().date()==today and len(past)==1344
        assert past.loc[(past.Block_ID=='B07')&(past.Disease_Name=='Red Rust')&
                        (past.Date.eq(pd.Timestamp(today))),'Sample_Incidence_Pct'].iloc[0]==10
        print('PASS: Historical 21-day source genuinely read, time aligned; current observation not yet overlaid')
        check={}
        def fake_prepare(r,o,updates,*,source_csv=None,**kwargs):
            assert r==root and o==today and source_csv is not None
            source=pd.read_csv(source_csv)
            assert len(source)==1344 and str(source['Date'].max())==today.isoformat()
            assert updates[-1]['block_id']=='B07' and updates[-1]['incidence_percent']==35
            check['inputs_are_real_historical_rows']=source['T2M'].eq(25).all()
            check['today_update_passed_separately']=True
            return {'prepared':'mocked train-fitted preprocessor'}
        dummy_arrays=(np.zeros((14,16,48),dtype=np.float32), np.zeros((16,48),dtype=np.float32))
        predictor=InstrumentedPredictor()
        with patch.object(s,'prepare_24h_inputs',side_effect=fake_prepare),patch.object(s,'arrays_for_disease',return_value=dummy_arrays):
            for disease in s.DISEASES:
                result=s.seasonal_predict(root,'B07',disease,100,35,today=today,predictor=predictor)
                assert result['forecast_origin_date']==today.isoformat()
                assert [r['forecast_target_date'] for r in result['selected_block_daily_forecast']]==[
                    (today+timedelta(days=i)).isoformat() for i in range(1,8)]
                assert len(result['all_block_forecast_for_selected_disease'])==112
                assert result['other_blocks_observed_today'] is False
                assert result['current_climate_observed'] is False
                assert result['saved'] is False
            assert check['inputs_are_real_historical_rows'] and check['today_update_passed_separately']
            assert not (root/s.OBSERVATIONS_FILE).exists()
            print('PASS: All four diseases, all blocks, Day 1..7 dates, preview never saved')
            saved=s.seasonal_predict(root,'B07','Red Rust',100,35,save=True,today=today,predictor=predictor)
            assert saved['saved'] and s.seasonal_observations(root)['count']==1
            assert not (root/'data/runtime/officer_observations.csv').exists()
            assert not (root/'outputs/dashboard/dynamic/step42_latest_officer_forecast.json').exists()
            print('PASS: Save isolated to Step52 files; previous forecasting files untouched')
        try: s.seasonal_predict(root,'B55','Red Rust',100,35,today=today,predictor=predictor)
        except ValueError: pass
        else: raise AssertionError('Bad block ID not rejected')
        try: s.seasonal_predict(root,'B07','Healthy',100,35,today=today,predictor=predictor)
        except ValueError: pass
        else: raise AssertionError('Healthy must not be considered spread disease')
        print('PASS: Invalid block and healthy class rejected')
    print('STEP52 SEASONAL-CONTEXT 7-DAY CODE VERIFY — PASS')
    print('NOTE: No independent field validation or real saved-model inference was run in this isolated test.')

if __name__=='__main__':main()
