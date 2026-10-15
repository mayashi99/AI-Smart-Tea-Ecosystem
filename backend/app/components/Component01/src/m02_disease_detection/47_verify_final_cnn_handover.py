"""Check Step47 best selected checkpoint + Grad-CAM++ without reopening dev_test.

Requires the source CNN scripts, Step47 image API compatibility update, model
files and the original 5-class dataset. Never retrains or alters checkpoints.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
XAI = ROOT/'src/m05_explainability_alerts'
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(XAI))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-id', required=True)
    p.add_argument('--skip-gradcam', action='store_true')
    p.add_argument('--cpu-threads', type=int, default=4)
    args = p.parse_args()
    import torch
    torch.set_num_threads(args.cpu_threads)
    reports = ROOT/'outputs/reports/cnn_step47'/args.run_id
    chosen_file = reports/'final_selected_checkpoint.json'
    if not chosen_file.is_file():
        raise FileNotFoundError('Run 47_evaluate_selected_cnn.py first (one-time development test).')
    decision = json.loads(chosen_file.read_text(encoding='utf-8'))
    checkpoint = ROOT/decision['checkpoint']
    if not checkpoint.is_file():
        raise FileNotFoundError(checkpoint)
    from cnn_inference import CNNPredictor
    predictor = CNNPredictor.from_step17_checkpoint(checkpoint, root=ROOT, device='cpu')
    labels = ['brown blight', 'grey leaf', 'healthy', 'red rust', 'red spider mite']
    if predictor.classes != labels:
        raise RuntimeError('Wrong class order')
    manifest = ROOT/'data/processed/image_split_manifest_DEV_ONLY.csv'
    with manifest.open(encoding='utf-8-sig', newline='') as fh:
        sample = next((r for r in csv.DictReader(fh) if r.get('split') == 'dev_train'), None)
    if sample is None:
        raise ValueError('No train image in development manifest')
    photo = ROOT/sample['relative_path']
    prediction = predictor.predict(photo, top_k=3)
    if len(prediction['top_k']) != 3 or prediction['predicted_class'] not in labels:
        raise RuntimeError('CNN inference returned unexpected class mapping')
    print(f'PASS: 5-class checkpoint loaded, architecture={decision["architecture"]}, predicted={prediction["predicted_class"]}')
    if not args.skip_gradcam:
        from gradcam_plus_plus import explain_leaf_image
        result = explain_leaf_image(photo, root=ROOT, checkpoint=checkpoint,
                                    output_dir=reports/'verification_gradcam_images',device='cpu')
        for key in ('overlay_png','heatmap_png'):
            if not Path(result[key]).is_file():
                raise RuntimeError('GradCAM image missing: '+key)
        print('PASS: Grad-CAM++ PNG overlays/heatmap generated for selected architecture')
    audit = json.loads((reports/'dev_test_evaluation.json').read_text(encoding='utf-8'))
    seal = json.loads((reports/'dev_test_sealed.json').read_text(encoding='utf-8'))
    if audit['evaluated_once'] is not True or seal['test_source_independence_verified'] is not False:
        raise RuntimeError('Diagnostic-test status differs from expected development-only status')
    print('STEP47 HANDOVER VERIFY — PASS; development dataset only, NO field accuracy claims.')
    print('Use in the FastAPI terminal (PowerShell):')
    print(f'$env:TEA_CNN_CHECKPOINT = "{decision["checkpoint"]}"')


if __name__ == '__main__':
    main()
