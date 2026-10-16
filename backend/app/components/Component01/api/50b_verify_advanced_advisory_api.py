"""Step 50B — offline API contract verification without actual CNN inference.

Run from the repository root using the activated Component01 .venv:
  python backend/app/components/Component01/api/50b_verify_advanced_advisory_api.py

Do NOT change any training data, CNN checkpoint, officer CSV, or forecast JSON.
"""
from __future__ import annotations

from pathlib import Path
import sys

COMPONENT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COMPONENT_ROOT / 'src' / 'm05_explainability_alerts'))
sys.path.insert(0, str(COMPONENT_ROOT / 'api'))

from advanced_disease_advisory import (  # noqa: E402
    AdvancedAdvisoryRequest, build_advanced_disease_advisory, supported_classes,
)
from fastapi.testclient import TestClient  # noqa: E402
from step45_app import app  # noqa: E402

CLASSES = ['brown blight', 'grey leaf', 'healthy', 'red rust', 'red spider mite']


def _safe_plan(plan: dict) -> None:
    chem = plan['chemical_control']
    assert chem['recommended_products'] == [], plan
    assert chem['active_ingredients'] == [], plan
    assert chem['dosage'] is None, plan
    assert chem['application_schedule'] is None, plan
    assert chem['automatic_treatment_authorized'] is False
    assert plan['agronomist_approval_verified_by_system'] is False
    assert plan['field_validation_completed'] is False
    assert plan['severity_assessment']['auto_calculated'] is False


def run() -> None:
    assert supported_classes() == CLASSES
    for disease in CLASSES:
        plan = build_advanced_disease_advisory(disease)
        assert plan['disease_name'] == disease
        assert plan['severity_assessment']['level'] is None
        assert plan['field_assessment_status'] == 'not_assessed'
        assert plan['field_context']['observed_incidence_percent'] is None
        assert plan['management_actions']
        assert plan['follow_up_plan']['record_fields']
        _safe_plan(plan)
    print('PASS: five disease-specific extended plans; no auto-chemicals')

    request = AdvancedAdvisoryRequest(
        disease_name='Red Rust', field_assessment='officer_observation',
        severity_level='high', block_id='B07',
        inspected_bushes=100, symptomatic_bushes=35,
    )
    plan = build_advanced_disease_advisory(**request.model_dump())
    assert plan['field_context']['observed_incidence_percent'] == 35.0
    assert plan['severity_assessment']['source'] == 'USER_REPORTED_FIELD_ASSESSMENT'
    assert plan['follow_up_plan']['priority'] == 'PROMPT_EXPERT_ESCALATION'
    _safe_plan(plan)
    print('PASS: human-reported B07 severity and 35% observed incidence kept distinct')

    # Confirm the *real* Step45 API routes are registered in the local repo.
    with TestClient(app) as client:
        r = client.get('/api/advisory/classes')
        assert r.status_code == 200 and r.json()['classes'] == CLASSES, r.text
        for disease in CLASSES:
            response = client.post('/api/advisory/advanced', json={'disease_name': disease})
            assert response.status_code == 200, (disease, response.text)
            assert response.json()['disease_name'] == disease
            _safe_plan(response.json())
        print('PASS: POST /api/advisory/advanced for five CNN classes')

        response = client.post('/api/advisory/advanced', json=request.model_dump())
        assert response.status_code == 200, response.text
        assert response.json()['field_context']['observed_incidence_percent'] == 35.0
        assert response.json()['severity_assessment']['level'] == 'high'
        print('PASS: officer-entered observation + advanced JSON response')

        healthy_conflict = client.post('/api/advisory/advanced', json={
            'disease_name': 'healthy', 'field_assessment': 'officer_observation',
            'inspected_bushes': 10, 'symptomatic_bushes': 3,
        })
        assert healthy_conflict.status_code == 200, healthy_conflict.text
        assert healthy_conflict.json()['field_image_disagreement'] is True
        print('PASS: healthy-image/field-symptom disagreement flagged')

        invalid_cases = [
            {'disease_name': 'white spot'},
            {'disease_name': 'red rust', 'severity_level': 'high'},
            {'disease_name': 'red rust', 'inspected_bushes': 100},
            {'disease_name': 'red rust', 'inspected_bushes': 10, 'symptomatic_bushes': 11},
            {'disease_name': 'red rust', 'inspected_bushes': 0, 'symptomatic_bushes': 0},
            {'disease_name': 'healthy', 'field_assessment': 'officer_observation', 'severity_level': 'low'},
            {'disease_name': 'grey leaf', 'unexpected_client_override': True},
        ]
        for item in invalid_cases:
            response = client.post('/api/advisory/advanced', json=item)
            assert response.status_code == 422, (item, response.status_code, response.text)
        print(f'PASS: {len(invalid_cases)} input validation cases rejected with HTTP 422')

        old = client.get('/api/advisory/grey%20leaf')
        assert old.status_code == 200 and old.json()['advisory_version'] == '50.1.0'
        print('PASS: old Step50 endpoint and response contract preserved')

    print('STEP50B ADVANCED ADVISORY API VERIFY — PASS')
    print('NOTE: Run Step46 QUICK separately to test real CNN, Grad-CAM++ and M4 models.')


if __name__ == '__main__':
    run()
