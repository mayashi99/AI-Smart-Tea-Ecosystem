"""Step 44 — verify Grad-CAM++ pipeline against existing local 5-class dev CNN.

Does not use dev_val/dev_test and does not retrain. Writes only output assets.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from PIL import Image
from gradcam_plus_plus import component_root, explain_leaf_image, choose_target
from importlib import util


def run() -> None:
    root = component_root()
    script = Path(__file__).with_name('44_generate_gradcam_pp.py')
    spec = util.spec_from_file_location('step44_cli', script)
    if spec is None or spec.loader is None:
        raise RuntimeError('Cannot import step44 CLI helper')
    mod = util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    image = mod.first_development_train_image(root)
    old_hash = hashlib.sha256(image.read_bytes()).hexdigest()
    result = explain_leaf_image(image, root=root, device='cpu')
    assert result['architecture'] == 'mobilenet_v3_small'
    assert len(result['class_names']) == 5
    assert result['predicted_class'] == result['explained_class']
    assert result['uncalibrated_softmax_score'] >= 0
    assert len(result['top_k']) == 3
    assert result['is_leaf_lesion_segmentation'] is False
    assert result['is_leaf_area_severity_percentage'] is False
    assert hashlib.sha256(image.read_bytes()).hexdigest() == old_hash, 'Input image modified!'
    with Image.open(result['overlay_png']) as f:
        assert f.size == (result['image_width'], result['image_height']) and f.mode == 'RGB'
    with Image.open(result['heatmap_png']) as f:
        assert f.size == (result['image_width'], result['image_height']) and f.mode == 'L'
    saved = json.loads(Path(result['metadata_json']).read_text(encoding='utf-8'))
    assert saved['input_sha256'] == old_hash
    assert len(saved['class_names']) == 5
    try:
        choose_target(result['class_names'], 'White Spot', 0)
    except ValueError:
        pass
    else:
        raise AssertionError('Deferred White Spot class should be rejected')
    try:
        choose_target(result['class_names'], 5, 0)
    except ValueError:
        pass
    else:
        raise AssertionError('Out-of-range target index should be rejected')
    print('='*78)
    print('STEP 44 VERIFY - 5-CLASS GRAD-CAM++ | DEVELOPMENT-ONLY')
    print('='*78)
    print(f"PASS: CNN architecture + 5-class checkpoint accepted; predicted={result['predicted_class']}")
    print('PASS: gradient-based explanation executed, images are original dimensions')
    print('PASS: White Spot/out-of-range targets rejected; source unchanged')
    print('PASS: metadata flags distinguish attribution from lesion severity or diagnosis')
    print('Overlay:', result['overlay_png'])
    print('Metadata:', result['metadata_json'])
    print('WARNING: random-init CNN results are for plumbing only; field accuracy not measured')


if __name__ == '__main__':
    run()
