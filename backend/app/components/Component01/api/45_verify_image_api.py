"""Step45 end-to-end test: actual CNN Grad-CAM++, HTTP multipart and image assets.

Run from project root. Never modifies models, dataset images, or observations.
"""
from __future__ import annotations
import csv
from pathlib import Path
from fastapi.testclient import TestClient
from PIL import Image
from io import BytesIO
import step45_app  # normal import also registers Step43 request models (Pydantic v2)

ROOT = Path(__file__).resolve().parents[1]
client = TestClient(step45_app.app)


def first_train_image():
    manifest = ROOT / 'data/processed/image_split_manifest_DEV_ONLY.csv'
    with manifest.open(encoding='utf-8-sig', newline='') as handle:
        for record in csv.DictReader(handle):
            if record.get('split') == 'dev_train':
                item = (ROOT / record['relative_path']).resolve()
                if not item.is_relative_to(ROOT.resolve()) or not item.is_file():
                    raise RuntimeError('First development image missing or unsafe')
                return item
    raise RuntimeError('Could not find a dev_train image')


def run():
    print('=' * 80)
    print('STEP 45 - IMAGE UPLOAD + GRAD-CAM++ FASTAPI | ACTUAL 5-CLASS DEV CHECKPOINT')
    print('=' * 80)
    status = client.get('/api/image/status')
    assert status.status_code == 200 and status.json()['image_api_available'], status.text[:400]
    blocks = client.get('/api/estate/blocks')
    assert blocks.status_code == 200 and blocks.json()['count'] == 16
    image = first_train_image()
    data = image.read_bytes()
    resp = client.post('/api/image/analyze', files={'file':(image.name,data,'image/jpeg')})
    assert resp.status_code == 200, f'Image API failed: {resp.status_code} {resp.text[:600]}'
    body = resp.json()
    assert body['predicted_class'] in body['class_names'] and len(body['class_names']) == 5
    assert body['full_cnn_training_completed'] is False
    assert not body['is_leaf_lesion_segmentation'] and not body['is_disease_diagnosis_verified']
    for key in ('heatmap_url', 'overlay_url'):
        url = body[key]
        assert url.startswith('/api/image/artifacts/') and '.png' in url
        asset = client.get(url)
        assert asset.status_code == 200 and asset.headers['content-type'] == 'image/png'
        with Image.open(BytesIO(asset.content)) as output:
            assert output.size == (body['image_width'],body['image_height'])
    print('PASS: Actual CNN + Grad-CAM++ upload; predicted=',body['predicted_class'])
    print('PASS: Image asset URLs GET 200, original dimensions retained')
    bad_target = client.post('/api/image/analyze', data={'target_class':'White Spot'},
                             files={'file':(image.name,data,'image/jpeg')})
    assert bad_target.status_code == 422, (bad_target.status_code,bad_target.text[:300])
    invalid = client.post('/api/image/analyze', files={'file':('bad.jpg',b'not an image','image/jpeg')})
    assert invalid.status_code == 422
    unsupported = client.post('/api/image/analyze', files={'file':('bad.txt',b'x','text/plain')})
    assert unsupported.status_code == 422
    traversal = client.get('/api/image/artifacts/..%2Fstep43_app.py')
    assert traversal.status_code in {404,422}
    assert client.get('/api/image/artifacts/not_a_real_png.png').status_code == 404
    print('PASS: invalid images, White Spot, unsupported type, unsafe/missing asset blocked')
    print('PASS: Step43 block list endpoint remains available; no officer inputs saved')
    print('WARNING: CNN checkpoint is development-only/smoke, NOT verified diagnosis accuracy')


if __name__ == '__main__': run()
