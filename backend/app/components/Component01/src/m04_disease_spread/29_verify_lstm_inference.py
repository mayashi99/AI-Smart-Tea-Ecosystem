"""Verify newest Step29 LSTM checkpoint on one historical VALIDATION input window."""
import argparse
from pathlib import Path
from multidisease_lstm_inference import predict_scaled_block_window
from spread_sequence_loader import load_bundle, extract_sample


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path)
    p.add_argument('--run-dir', type=Path)
    args = p.parse_args()
    root = (args.root or Path(__file__).resolve().parents[2]).resolve()
    base = root / 'models/spread/multidisease_step29'
    directories = [x for x in base.glob('*') if (x / 'manifest.json').is_file()]
    if not directories:
        raise RuntimeError('No Step29 checkpoints available; train first')
    run = args.run_dir or max(directories, key=lambda x: (x / 'manifest.json').stat().st_mtime_ns)
    data = load_bundle(root, 'validation')
    x, _, _, date = extract_sample(data, 0, block_index=0)
    result = predict_scaled_block_window(run, x)
    assert len(result['forecast_days']) == 7
    assert all(0 <= v['disease_active_probability'] <= 1 and 0 <= v['new_onset_probability'] <= 1 and 0 <= v['incidence_percent'] <= 100 for v in result['forecast_days'])
    print('STEP 29 - LSTM SAVED CHECKPOINT INFERENCE VERIFICATION')
    print('Checkpoint:', run)
    print('Validation origin:', date)
    print('Example Day 1:', result['forecast_days'][0])
    print('PASS: 7 days of numeric predictions; original test set not used')
    print('WARNING: simulation-only; not a validated disease diagnosis or field forecast')


if __name__ == '__main__':
    main()
