"""Suitability control-flow tests and real tea smoke checks; no persistent artifacts.

Generated document/graphic fixtures exercise rules, not real-world accuracy.
Use --real-cnn to exercise the unchanged classifier on one real tea photograph.
"""
import argparse
import csv
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

import step45_app as api
from image_suitability import assess_image


def encoded(image):
    data = BytesIO()
    image.save(data, format='PNG')
    return data.getvalue()


def run(real_cnn=False, screenshot=None, persons=()):
    client = TestClient(api.app)
    for person in persons:
        photo = Path(person)
        with patch.object(api, 'explain_leaf_image') as cnn, \
             patch.object(api, 'build_disease_advisory') as basic, \
             patch.object(api, 'build_advanced_disease_advisory') as advanced:
            result = client.post('/api/image/analyze', files={'file': (photo.name, photo.read_bytes(), 'image/jpeg')})
            assert result.status_code == 200, result.text
            body = result.json()
            assert body['analysis_status'] == 'rejected', body
            assert body['suitability']['reason'] == 'HUMAN_FACE_DETECTED', body
            assert not {'predicted_class', 'top_k', 'heatmap_url', 'overlay_url', 'advisory', 'advanced_advisory'} & body.keys()
            cnn.assert_not_called(); basic.assert_not_called(); advanced.assert_not_called()
            print('PASS original person JPEG rejected, no inference/artifacts/advisories:', photo.name,
                  body['suitability']['face_safeguard']['detected_count'])
    blank = Image.new('RGB', (640, 480), 'white')
    document = blank.copy()
    draw = ImageDraw.Draw(document)
    for y in range(35, 430, 25):
        draw.text((30, y), 'Research presentation: quarterly financial statements', fill='black')
    fixtures = [('uniform', encoded(blank)), ('document', encoded(document))]
    graphic = Image.new('RGB', (640, 480), '#172e50')
    ImageDraw.Draw(graphic).rectangle((20, 20, 610, 150), fill='#4488cc')
    fixtures.append(('flat_slide', encoded(graphic)))
    if screenshot:
        photo = Path(screenshot)
        data = photo.read_bytes()
        with patch.object(api, 'explain_leaf_image') as cnn, \
             patch.object(api, 'build_disease_advisory') as basic, \
             patch.object(api, 'build_advanced_disease_advisory') as advanced:
            result = client.post('/api/image/analyze', files={'file': (photo.name, data, 'image/png')})
            assert result.status_code == 200, result.text
            body = result.json()
            assert body['analysis_status'] == 'rejected', body
            assert not {'predicted_class', 'top_k', 'heatmap_url', 'overlay_url', 'advisory', 'advanced_advisory'} & body.keys()
            cnn.assert_not_called(); basic.assert_not_called(); advanced.assert_not_called()
            print('PASS EXACT real screenshot rejected; CNN/Grad-CAM/advisories never called:', photo)
            print(body['suitability'])
    for name, data in fixtures:
        with patch.object(api, 'explain_leaf_image') as cnn, \
             patch.object(api, 'build_disease_advisory') as basic, \
             patch.object(api, 'build_advanced_disease_advisory') as advanced:
            result = client.post('/api/image/analyze', files={'file': ('fixture.png', data, 'image/png')})
            assert result.status_code == 200, result.text
            body = result.json()
            assert body['analysis_status'] in {'rejected', 'uncertain'}, body
            assert not {'predicted_class', 'top_k', 'heatmap_url', 'overlay_url', 'advisory', 'advanced_advisory'} & body.keys()
            cnn.assert_not_called(); basic.assert_not_called(); advanced.assert_not_called()
            print('PASS generated fixture:', name, body['analysis_status'])
    # Explicit uncertain branch is tested independently of threshold fixtures.
    with patch.object(api, 'assess_image', return_value={'analysis_status': 'uncertain'}), \
         patch.object(api, 'explain_leaf_image') as cnn:
        result = client.post('/api/image/analyze', files={'file': ('fixture.png', fixtures[0][1], 'image/png')})
        assert result.json()['analysis_status'] == 'uncertain'
        cnn.assert_not_called()
    for filename, data, mime, expected in [
        ('bad.jpg', b'corrupt', 'image/jpeg', 422),
        ('bad.txt', b'not an image', 'text/plain', 422),
        ('big.png', b'x' * (api.MAX_UPLOAD_BYTES + 1), 'image/png', 413),
        ('tiny.png', encoded(Image.new('RGB', (16, 16))), 'image/png', 422),
    ]:
        assert client.post('/api/image/analyze', files={'file': (filename, data, mime)}).status_code == expected
    print('PASS uncertain gate and existing invalid-format/size/dimension checks')
    with (api.ROOT / 'data/processed/image_split_manifest_DEV_ONLY.csv').open(encoding='utf-8-sig') as handle:
        rows = list(csv.DictReader(handle))
    samples = {}
    for row in rows:
        if row['split'] == 'dev_train':
            samples.setdefault(row['class_name'], api.ROOT / row['relative_path'])
    for label, photo in samples.items():
        result = assess_image(photo.read_bytes())
        assert result['analysis_status'] == 'acceptable', (label, result)
        print('PASS real tea appearance check:', label)
    if real_cnn:
        with TemporaryDirectory(prefix='tea_suitability_test_') as temporary, \
             patch.object(api, 'ASSET_DIR', Path(temporary)):
            for label, photo in samples.items():
                result = client.post('/api/image/analyze', files={'file': (photo.name, photo.read_bytes(), 'image/jpeg')})
                assert result.status_code == 200, result.text
                body = result.json()
                assert body['analysis_status'] == 'completed', body
                assert body['predicted_class'] in body['class_names']
                assert body['advisory'] and body['advanced_advisory']
                for key in ('heatmap_url', 'overlay_url'):
                    assert client.get(body[key]).status_code == 200
                print('PASS real CNN + Grad-CAM++ + both advisories:', label)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--real-cnn', action='store_true')
    parser.add_argument('--screenshot', type=Path, help='Actual screenshot to test, without copying it')
    parser.add_argument('--person', type=Path, action='append', default=[], help='Original person JPEG; repeat for multiple images')
    args = parser.parse_args()
    run(args.real_cnn, args.screenshot, args.person)
