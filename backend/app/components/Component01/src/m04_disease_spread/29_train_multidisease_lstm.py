"""Step 29: Per-block LSTM seven-day forecast for synthetic four-disease data.

Validation-only early stopping; NO test loading, tuning, or test reporting.
Run Step 27 first. Predictions use 14 past days of 48 pre-scaled features.
"""
from __future__ import annotations
import argparse
from datetime import datetime
import json
from pathlib import Path
import random
import sys
import time

import numpy as np
import torch
from torch.utils.data import DataLoader, Subset
from sklearn.metrics import f1_score, mean_absolute_error

from spread_sequence_loader import SpreadSequenceDataset
from multidisease_lstm_inference import BlockForecastLSTM, decode_predictions


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def root_from_script():
    return Path(__file__).resolve().parents[2]


def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def make_dataset(root, split, mode, seed):
    ds = SpreadSequenceDataset(root, split, mode='block')
    require(len(ds.bundle['contract']['input_feature_columns']) == 48, 'Expected 48 features')
    require(ds.bundle['contract']['sequence_days'] == 14, 'Expected 14 day lookback')
    require(len(ds.bundle['contract']['disease_names']) == 4, 'Expected four diseases')
    if mode == 'smoke':
        # Distinct sample indices, balanced across four diseases, with no test usage.
        rng = np.random.default_rng(seed + (1 if split == 'validation' else 0))
        pool = ds.bundle['sample_indices']
        selected = []
        n_per_disease = 96 if split == 'train' else 32
        for disease_idx in range(4):
            seq_pool = np.flatnonzero(pool[:, 1] == disease_idx)
            pick = rng.choice(seq_pool, size=min(n_per_disease, len(seq_pool)), replace=False)
            for seq_id in pick.tolist():
                block_id = int(rng.integers(0, 16))
                selected.append(seq_id * 16 + block_id)
        if split == 'validation':
            selected.sort()
        else:
            rng.shuffle(selected)
        return Subset(ds, selected)
    return ds


def disease_labels_for_dataset(dataset):
    if isinstance(dataset, Subset):
        indices, base = np.array(dataset.indices, dtype=int), dataset.dataset
    else:
        indices, base = np.arange(len(dataset), dtype=int), dataset
    seq_indices = indices // 16
    return base.bundle['sample_indices'][seq_indices, 1].astype(int)


def calculate_class_weights(dataset):
    # Training set labels only. For loss weighting; no validation/test labels.
    base = dataset.dataset if isinstance(dataset, Subset) else dataset
    ids = dataset.indices if isinstance(dataset, Subset) else range(len(dataset))
    sums, total = np.zeros(2, dtype=np.float64), 0
    for index in ids:
        seq_id, block_id = divmod(int(index), 16)
        end, dis = base.bundle['sample_indices'][seq_id]
        vals = base.bundle['Y_days'][int(end), int(dis), block_id, :, [0, 2]]
        sums += np.asarray(vals).sum(axis=0) if vals.shape == (7, 2) else np.asarray(vals).sum(axis=1)
        total += 7
    return torch.tensor(np.clip((total - sums) / np.maximum(1, sums), 1, 10), dtype=torch.float32)


def loss_fn(raw, target, pos_weights):
    # Correct target order: disease_active(0), incidence_percent(1), new_onset(2).
    require(target.shape[-2:] == (7, 3), 'Target label dimensions changed')
    classification = torch.nn.functional.binary_cross_entropy_with_logits
    active = classification(raw[:, :, 0], target[:, :, 0], pos_weight=pos_weights[0])
    onset = classification(raw[:, :, 2], target[:, :, 2], pos_weight=pos_weights[1])
    # Incidence is a percentage; normalize to [0,1] for stable multi-task loss.
    incidence = torch.nn.functional.smooth_l1_loss(torch.sigmoid(raw[:, :, 1]), target[:, :, 1] / 100.0, beta=0.05)
    return active + onset + 3 * incidence


def run_epoch(model, loader, optimizer, device, pos_weights):
    train = optimizer is not None
    model.train(train)
    total_loss, count = 0.0, 0
    for x, y in loader:
        x = x.to(device=device, dtype=torch.float32)
        y = y.to(device=device, dtype=torch.float32)
        require(torch.isfinite(x).all().item() and torch.isfinite(y).all().item(), 'Nonfinite input/labels')
        if train:
            optimizer.zero_grad(set_to_none=True)
        with torch.set_grad_enabled(train):
            raw = model(x)
            loss = loss_fn(raw, y, pos_weights)
            if train:
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 2.0)
                optimizer.step()
        total_loss += float(loss.item()) * len(x)
        count += len(x)
    return total_loss / max(1, count)


def validate_predictions(model, loader, dataset, device):
    model.eval()
    predictions, actual = [], []
    with torch.inference_mode():
        for x, y in loader:
            output = decode_predictions(model(x.to(device=device, dtype=torch.float32)))
            predictions.append(output.cpu().numpy())
            actual.append(y.numpy())
    preds, true = np.concatenate(predictions), np.concatenate(actual)
    labels = disease_labels_for_dataset(dataset)
    require(len(labels) == len(preds), 'Validation sample order mismatch')
    disease_names = (dataset.dataset if isinstance(dataset, Subset) else dataset).bundle['contract']['disease_names']
    report = []
    for disease_idx, disease in enumerate(disease_names):
        mask = (labels == disease_idx)
        require(mask.any(), f'No validation sample for {disease}')
        for day in range(7):
            report.append({
                'disease': disease, 'day': day + 1, 'records': int(mask.sum()),
                'activity_macro_f1': float(f1_score(true[mask, day, 0] >= .5, preds[mask, day, 0] >= .5, labels=[False, True], average='macro', zero_division=0)),
                'new_onset_macro_f1': float(f1_score(true[mask, day, 2] >= .5, preds[mask, day, 2] >= .5, labels=[False, True], average='macro', zero_division=0)),
                'incidence_mae': float(mean_absolute_error(true[mask, day, 1], preds[mask, day, 1])),
            })
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode', choices=('smoke', 'full'), default='smoke')
    p.add_argument('--epochs', type=int, default=None)
    p.add_argument('--batch-size', type=int, default=128)
    p.add_argument('--device', default='cpu', choices=('cpu', 'cuda'))
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--root', type=Path)
    p.add_argument('--threads', type=int, default=2)
    args = p.parse_args()
    require(1 <= args.batch_size <= 2048 and 1 <= args.threads <= 32, 'Invalid batch size/threads')
    if args.device == 'cuda':
        require(torch.cuda.is_available(), 'CUDA requested but unavailable')
    torch.set_num_threads(args.threads)
    random.seed(args.seed); np.random.seed(args.seed); torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
    root = (args.root or root_from_script()).resolve()
    require((root / 'data/processed/multidisease_sequence_graph_contract.json').is_file(), 'Run Step27 first')
    train_ds = make_dataset(root, 'train', args.mode, args.seed)
    val_ds = make_dataset(root, 'validation', args.mode, args.seed)
    # Intentionally NEVER instantiates test dataset in Step29.
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, num_workers=0)
    pos_weights = calculate_class_weights(train_ds).to(args.device)
    architecture = {'input_size': 48, 'hidden_size': 48, 'num_layers': 1, 'dropout': 0.0}
    model = BlockForecastLSTM(**architecture).to(args.device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.001, weight_decay=0.0001)
    epochs = args.epochs or (1 if args.mode == 'smoke' else 10)
    require(1 <= epochs <= 200, 'Invalid epoch count')
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    run_dir = root / 'models/spread/multidisease_step29' / f'{args.mode}_{stamp}'
    report_dir = root / 'outputs/reports/multidisease_step29' / f'{args.mode}_{stamp}'
    run_dir.mkdir(parents=True, exist_ok=False); report_dir.mkdir(parents=True, exist_ok=False)
    best, history, stale = float('inf'), [], 0
    print('=' * 72, flush=True)
    print(f'STEP 29 - MULTI-DISEASE BLOCK LSTM | {args.mode.upper()} | SIMULATION', flush=True)
    print('=' * 72, flush=True)
    print(f'train={len(train_ds)} validation={len(val_ds)} | lookback=14 forecast=7 | features=48', flush=True)
    print('Selection: lowest validation multi-task loss; TEST not loaded', flush=True)
    start = time.monotonic()
    for epoch in range(1, epochs + 1):
        train_loss = run_epoch(model, train_loader, optimizer, args.device, pos_weights)
        val_loss = run_epoch(model, val_loader, None, args.device, pos_weights)
        improved = val_loss < best - 1e-5
        if improved:
            best = val_loss; stale = 0
            torch.save({'state_dict': model.state_dict()}, run_dir / 'best_lstm_weights.pt')
        else:
            stale += 1
        history.append({'epoch': epoch, 'train_loss': train_loss, 'validation_loss': val_loss})
        print(f'epoch {epoch:02}/{epochs} train_loss={train_loss:.5f} val_loss={val_loss:.5f} best_val={best:.5f}', flush=True)
        if args.mode == 'full' and stale >= 3:
            print('Early stopping (3 epochs without validation loss improvement)', flush=True)
            break
    checkpoint = torch.load(run_dir / 'best_lstm_weights.pt', map_location=args.device, weights_only=True)
    model.load_state_dict(checkpoint['state_dict'])
    metrics = validate_predictions(model, val_loader, val_ds, args.device)
    import csv
    with (report_dir / 'validation_metrics_by_disease_and_day.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(metrics[0]))
        writer.writeheader(); writer.writerows(metrics)
    with (report_dir / 'training_history.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(history[0]))
        writer.writeheader(); writer.writerows(history)
    contract = (train_ds.dataset if isinstance(train_ds, Subset) else train_ds).bundle['contract']
    manifest = {
        'schema_version': 'step29-v1', 'scope': 'SIMULATION_ONLY_4_DISEASES',
        'model_type': 'PER_BLOCK_LSTM_NO_GRAPH',
        'checkpoint': 'best_lstm_weights.pt', 'architecture': architecture,
        'feature_count': 48, 'lookback_days': 14, 'forecast_days': 7,
        'disease_names': contract['disease_names'], 'block_ids': contract['block_ids'],
        'preprocessing_contract': 'data/processed/multidisease_feature_contract.json',
        'sequence_contract': 'data/processed/multidisease_sequence_graph_contract.json',
        'loss_weights_from_training_only': pos_weights.cpu().tolist(),
        'validation_best_loss': best, 'epochs_completed': len(history),
        'samples': {'train': len(train_ds), 'validation': len(val_ds)},
        'test_evaluated': False, 'model_selection_basis': 'validation_loss_only',
        'real_world_validation': False,
        'notes': 'Synthetic disease labels and mock estate geometry. Not field validated. Inference input requires Step26 train scaling.',
    }
    save_json(run_dir / 'manifest.json', manifest)
    save_json(report_dir / 'step29_summary.json', {'status': 'PASS_LSTM_TRAINING', 'run': str(run_dir),
        'best_validation_loss': best, 'metrics_by_disease_and_day': str(report_dir / 'validation_metrics_by_disease_and_day.csv'),
        'elapsed_seconds': round(time.monotonic() - start, 2), 'test_evaluated': False})
    print('PASS: saved checkpoint, 28 disease/day validation metric rows; TEST NOT USED', flush=True)
    print('Model:', run_dir, flush=True)
    print('Reports:', report_dir, flush=True)
    print('WARNING: synthetic disease histories, no real-world validation', flush=True)


if __name__ == '__main__':
    main()
