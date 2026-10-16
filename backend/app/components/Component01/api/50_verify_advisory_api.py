"""Step 50 advisory-only regression (no CNN inference, training, or file writes)."""
from __future__ import annotations

from fastapi.testclient import TestClient
from step45_app import app

CLASSES = ['brown blight', 'grey leaf', 'healthy', 'red rust', 'red spider mite']


def main() -> None:
    with TestClient(app) as client:
        r = client.get('/api/advisory/classes')
        assert r.status_code == 200, (r.status_code, r.text)
        assert r.json()['classes'] == CLASSES
        print('PASS: GET /api/advisory/classes = 5 exact image classes')

        for cls in CLASSES:
            response = client.get('/api/advisory/' + cls.replace(' ', '%20'))
            assert response.status_code == 200, (cls, response.status_code, response.text)
            advisory = response.json()
            assert advisory['predicted_class'] == cls
            assert advisory['advisory_type'] == 'GENERAL_IPM_INFORMATION_ONLY'
            assert advisory['diagnosis_verified'] is False
            assert advisory['expert_review_status'] == 'TEMPLATE_PENDING_ESTATE_AGRONOMIST_REVIEW'
            assert advisory['field_validated'] is False
            assert advisory['immediate_checks'] and advisory['non_chemical_actions']
            chemical = advisory['chemical_guidance']
            assert chemical['recommended_products'] == []
            assert chemical['active_ingredients'] == []
            assert chemical['dosage'] is None and chemical['application_schedule'] is None
            assert chemical['status'] == ('NOT_INDICATED' if cls == 'healthy' else 'EXPERT_AND_REGISTRATION_CHECK_REQUIRED')
            print('PASS: advisory for ' + cls + ' (no automatic pesticide)')

        bad = client.get('/api/advisory/unknown-disease')
        assert bad.status_code == 422, (bad.status_code, bad.text)
        print('PASS: unknown class rejected with 422')

    print('STEP50 ADVISORY API VERIFY — PASS; existing CNN/M3/M4/M5 models untouched')


if __name__ == '__main__':
    main()
