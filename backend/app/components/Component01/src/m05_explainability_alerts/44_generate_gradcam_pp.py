"""Step 44 — Generate 5-class MobileNetV3 Small Grad-CAM++ explanation.

From E:\\J26-IT-415 repository root:
 python backend\\app\\components\\Component01\\src\\m05_explainability_alerts\\44_generate_gradcam_pp.py
 python backend\\app\\components\\Component01\\src\\m05_explainability_alerts\\44_generate_gradcam_pp.py --image "C:\\path\\to\\leaf.jpg" --target-class "Red Rust"
"""
from __future__ import annotations
import argparse
import csv
from pathlib import Path
from gradcam_plus_plus import component_root, explain_leaf_image


def first_development_train_image(root: Path) -> Path:
    manifest = root / 'data/processed/image_split_manifest_DEV_ONLY.csv'
    with manifest.open(encoding='utf-8-sig', newline='') as fp:
        for r in csv.DictReader(fp):
            if r.get('split') == 'dev_train':
                f = (root / r['relative_path']).resolve()
                if not f.is_relative_to(root.resolve()):
                    raise ValueError('Unsafe relative image path in manifest')
                if not f.is_file():
                    raise FileNotFoundError(f'Manifest image missing: {f}')
                return f
    raise ValueError('No dev_train image in manifest')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--image', help='Image path; defaults to first dev_train image from manifest')
    p.add_argument('--checkpoint', help='Path to 5-class checkpoint; default: latest compatible')
    p.add_argument('--target-class', help='Optional one of 5 classes, otherwise predicted class')
    p.add_argument('--device', default='auto', choices=['auto','cpu','cuda'])
    p.add_argument('--output-dir', default=None, help='Optional output directory')
    args = p.parse_args()
    root = component_root()
    file = args.image or first_development_train_image(root)
    result = explain_leaf_image(file, checkpoint=args.checkpoint, target_class=args.target_class,
                                device=args.device, output_dir=args.output_dir, root=root)
    print('='*78)
    print('STEP 44 - 5-CLASS GRAD-CAM++ IMAGE EXPLANATION | DEVELOPMENT ONLY')
    print('='*78)
    print('Input image:', result['input_image'])
    print('Architecture:', result['architecture'])
    print('Predicted class:', result['predicted_class'])
    print('Explained class:', result['explained_class'])
    print('Uncalibrated softmax:', result['uncalibrated_softmax_score'])
    print('Heatmap signal:', result['heatmap_signal_present'])
    print('Heatmap PNG:', result['heatmap_png'])
    print('Overlay PNG:', result['overlay_png'])
    print('Metadata JSON:', result['metadata_json'])
    print('PASS: checkpoint loaded, gradient attribution run, PNGs and metadata saved.')
    print('WARNING: NOT lesion segmentation, not leaf severity, not validated disease diagnosis.')


if __name__ == '__main__':
    main()
