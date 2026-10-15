"""Verify a Step30 saved checkpoint using VALIDATION features only, no test data."""
from pathlib import Path
import argparse
import json
import numpy as np
import torch

from spread_sequence_loader import load_bundle, extract_sample
from multidisease_gcn_lstm_inference import load_gcn_lstm, predict_scaled_graph_window


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path)
    p.add_argument('--run-dir', type=Path)
    args = p.parse_args()
    root = (args.root or Path(__file__).resolve().parents[2]).resolve()
    if args.run_dir:
        run = args.run_dir.resolve()
    else:
        base = root / 'models/spread/multidisease_step30'
        # Prefer full checkpoint if available, else newest smoke.
        runs = sorted([d for d in base.glob('full_*') if (d/'manifest.json').exists()])
        if not runs:
            runs = sorted([d for d in base.glob('smoke_*') if (d/'manifest.json').exists()])
        if not runs:
            raise RuntimeError('No Step30 saved model found; run training first')
        run = runs[-1]
    bundle = load_bundle(root, 'validation')  # NEVER load test
    window, _, _, origin = extract_sample(bundle, 0)
    _, disease_index = [int(v) for v in bundle['sample_indices'][0]]
    disease = bundle['contract']['disease_names'][disease_index]
    model, graph, manifest = load_gcn_lstm(run, component_root=root, device='cpu')
    result = predict_scaled_graph_window(run, window, disease, component_root=root, device='cpu')
    assert len(result['forecast_by_block']) == 16
    assert all(len(days) == 7 for days in result['forecast_by_block'].values())
    assert all(np.isfinite(entry['incidence_percent']) for days in result['forecast_by_block'].values() for entry in days)
    # Demonstrate that the learned model responds to adjacency, not just per-node inputs.
    with torch.inference_mode():
        input_window = torch.from_numpy(np.ascontiguousarray(window)).unsqueeze(0)
        full_graph = model(input_window, graph)
        isolated_graph = model(input_window, torch.eye(16))
    effect = float((full_graph - isolated_graph).abs().max().item())
    if effect < 1e-8:
        raise AssertionError('Changing graph does not affect output; check adjacency propagation')
    sample = result['forecast_by_block'][manifest['block_ids'][0]][0]
    print('STEP 30 - GCN-LSTM INFERENCE VERIFICATION')
    print('Checkpoint:', run)
    print('Validation origin:', origin, '| Disease:', disease)
    print('Graph influence sanity check (max abs logits difference):', round(effect, 6))
    print('Example Day 1, block', manifest['block_ids'][0], ':', json.dumps(sample))
    print('PASS: loaded GCN-LSTM, graph affects outputs, 16 blocks x 7 days predicted; TEST NOT USED')
    print('WARNING: simulation-only, no field validation')


if __name__ == '__main__':
    main()
