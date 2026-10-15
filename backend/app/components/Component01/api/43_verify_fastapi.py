"""Step43 in-process verification. Uses actual saved models, preview mode only.

Requires pip install fastapi uvicorn httpx. Never writes runtime observations.
Usage: python backend/app/components/Component01/api/43_verify_fastapi.py
"""
from __future__ import annotations

# Normal import registers the module in sys.modules, allowing Pydantic v2
# to resolve postponed type annotations for request bodies.
import step43_app as mod
from fastapi.testclient import TestClient

client=TestClient(mod.app)


def good(resp,where):
    assert resp.status_code==200, f'{where}: status={resp.status_code}, body={resp.text[:500]}'
    return resp.json()


def run():
    print('='*78)
    print('STEP43 - API CONTRACT + SAVED-MODEL PREVIEW TEST (NO FILE WRITES)')
    print('='*78)
    assert good(client.get('/health'),'health')['status']=='ready'
    assert len(good(client.get('/api/estate/blocks'),'blocks')['blocks'])==16
    assert len(good(client.get('/api/estate/diseases'),'diseases')['diseases'])==4
    m=good(client.get('/api/metadata'),'metadata')
    assert m['live_forecast'] is False
    summary=good(client.get('/api/dashboard/historical/overview'),'historical overview')
    history=good(client.get('/api/dashboard/historical/climate?limit=3'),'climate')
    assert len(history['monthly_records'])==3
    assert good(client.get('/api/alerts/historical/overview'),'alert overview')
    checks=0
    for i in range(1,17):
        block=f'B{i:02d}'
        b=good(client.get(f'/api/dashboard/historical/blocks/{block}'),'hist block '+block)
        assert len(b['seven_day_spread_forecasts'])==28
        a=good(client.get(f'/api/alerts/historical/blocks/{block}'),'alerts block '+block)
        assert len(a['daily_explanations'])==28
        checks+=1
    invalid=client.get('/api/dashboard/historical/blocks/B17')
    assert invalid.status_code==422
    for payload in [
        {'block_id':'B06','disease':'Red Rust','inspected_bushes':100,'symptomatic_bushes':20},
        {'block_id':'B16','disease':'Grey Leaf','inspected_bushes':80,'symptomatic_bushes':20},
    ]:
        inc=good(client.post('/api/severity/incidence',json=payload),'incidence')
        assert 0<=inc['incidence_percent']<=100
        result=good(client.post('/api/forecast/preview',json=payload),'ML preview')
        assert result['actual_saved_model_inference'] is True and result['saved'] is False
        assert len(result['selected_block_daily_forecast'])==7
        assert {r['horizon_day'] for r in result['selected_block_daily_forecast']}==set(range(1,8))
        assert result['selected_block_id']==payload['block_id']
        assert len(result['all_block_forecast_for_selected_disease'])==112
        print(f"MODEL PASS block={payload['block_id']} disease={payload['disease']} "+
              f"seven-day predictions=7 | 112 disease records | saved={result['saved']}")
    cases=[
        {'block_id':'B17','disease':'Red Rust','inspected_bushes':100,'symptomatic_bushes':10},
        {'block_id':'B01','disease':'Healthy','inspected_bushes':100,'symptomatic_bushes':10},
        {'block_id':'B01','disease':'Red Rust','inspected_bushes':10,'symptomatic_bushes':20},
        {'block_id':'B01','disease':'Red Rust','inspected_bushes':10.5,'symptomatic_bushes':2},
    ]
    for case in cases:
        assert client.post('/api/forecast/preview',json=case).status_code==422
    print(f'PASS: {checks}/16 historical block dashboards + alerts, 2 real model previews')
    print('PASS: all selected inputs validated; preview calls did NOT write new observations')
    print('NOTE: all forecasts are 2025 historical-origin synthetic simulation.')


if __name__=='__main__': run()
