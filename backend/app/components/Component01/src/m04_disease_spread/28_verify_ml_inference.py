"""Verify Step28 saved checkpoint using one held-out validation input row.
Does not consume test data. This is a functionality check, not valid accuracy.
"""
import argparse
import json
from pathlib import Path

import pandas as pd
from multidisease_ml_inference import MultiDiseaseBaselinePredictor


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--component-root', type=Path, default=Path(__file__).resolve().parents[2])
    p.add_argument('--manifest', type=Path, default=None)
    args = p.parse_args()
    root = args.component_root.resolve()
    if args.manifest:
        manifest = args.manifest
    else:
        model_root = root / 'models/spread/multidisease_step28'
        candidates = sorted(model_root.glob('full_*/manifest.json'), key=lambda x: x.parent.name)
        if not candidates:
            candidates = sorted(model_root.glob('smoke_*/manifest.json'), key=lambda x: x.parent.name)
        if not candidates:
            raise RuntimeError('Run Step28 training first or provide --manifest PATH')
        manifest = candidates[-1]
    predictor = MultiDiseaseBaselinePredictor(manifest)
    selected = predictor.manifest['chosen'][0]['target']
    kind, day = selected.rsplit('_Day_', 1)
    kind = kind.removeprefix('Target_')
    row = pd.read_csv(root / 'data/processed/multidisease_features_validation.csv', nrows=1,
                      usecols=predictor.features)
    pred = predictor.predict(row.iloc[0].to_dict(), int(day), kind)
    print('=' * 68)
    print('STEP 28 — SAVED MODEL INFERENCE CHECK (VALIDATION INPUT ONLY)')
    print('=' * 68)
    print('Manifest:', manifest)
    print('Result:', json.dumps(pred, indent=2))
    print('PASS: selected model can load and predict from 48 precomputed features.')
    print('WARNING: model accuracy and real-world validity NOT established by this test.')


if __name__ == '__main__':
    main()
