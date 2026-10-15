"""Step 30: Graph Convolution + LSTM, synthetic four-disease 7-day forecasting.

Data: Step27 14-day, 16-node, 48-feature windows and NORMALIZED adjacency.
Uses train+validation ONLY. Never loads test split or scores test outcomes.
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime
import json
from pathlib import Path
import random
import time

import numpy as np
import torch
from sklearn.metrics import f1_score, mean_absolute_error
from torch.utils.data import DataLoader, Dataset

from spread_sequence_loader import load_bundle
from multidisease_gcn_lstm_inference import GraphTemporalForecast, decode_graph_outputs, adjacency_sha256


def ensure(condition, message):
    if not condition:
        raise RuntimeError(message)


def save_json(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')


class GraphSequenceDataset(Dataset):
    def __init__(self, root, split, mode, seed):
        self.bundle = load_bundle(root, split)
        self.indices = np.arange(len(self.bundle['sample_indices']), dtype=np.int32)
        if mode == 'smoke':
            rng = np.random.default_rng(seed + int(split == 'validation'))
            samples_per_disease = 16 if split == 'train' else 8
            groups = []
            for d in range(4):
                possible = self.indices[self.bundle['sample_indices'][:, 1] == d]
                ensure(len(possible) >= samples_per_disease, f'Insufficient samples for disease {d}')
                groups.append(rng.choice(possible, size=samples_per_disease, replace=False))
            self.indices = np.concatenate(groups).astype(np.int32)
            if split == 'train':
                rng.shuffle(self.indices)
        self.length = int(self.bundle['contract']['sequence_days'])
        ensure(self.length == 14, 'Expected 14-day windows')
        ensure(len(self.bundle['contract']['input_feature_columns']) == 48, 'Feature contract changed')
        ensure(len(self.bundle['contract']['disease_names']) == 4, 'Disease classes changed')
        ensure(len(self.bundle['contract']['block_ids']) == 16, 'Graph nodes changed')

    def __len__(self):
        return len(self.indices)

    def __getitem__(self, i):
        end, disease = [int(v) for v in self.bundle['sample_indices'][int(self.indices[i])]]
        x = self.bundle['X_days'][end - self.length + 1:end + 1, disease]
        y = self.bundle['Y_days'][end, disease]
        return (torch.from_numpy(np.ascontiguousarray(x)),
                torch.from_numpy(np.ascontiguousarray(y)),
                torch.tensor(disease, dtype=torch.int64))


def class_weights_from_train(ds):
    # Positive weights from TRAIN labels only. Both classes in all seven horizons.
    positive = np.zeros(2, dtype=np.float64)
    total = 0
    for index in ds.indices:
        end, disease = ds.bundle['sample_indices'][int(index)]
        target = ds.bundle['Y_days'][int(end), int(disease)]
        positive[0] += target[..., 0].sum()
        positive[1] += target[..., 2].sum()
        total += target.shape[0] * target.shape[1]
    return torch.as_tensor(np.clip((total - positive) / np.maximum(positive, 1), 1, 10), dtype=torch.float32)


def multitask_loss(logits, targets, weights):
    ensure(logits.shape == targets.shape and targets.shape[-2:] == (7, 3), 'Targets/logits shape mismatch')
    active = torch.nn.functional.binary_cross_entropy_with_logits(
        logits[..., 0], targets[..., 0], pos_weight=weights[0])
    onset = torch.nn.functional.binary_cross_entropy_with_logits(
        logits[..., 2], targets[..., 2], pos_weight=weights[1])
    incidence = torch.nn.functional.smooth_l1_loss(
        torch.sigmoid(logits[..., 1]), targets[..., 1] / 100, beta=0.05)
    return active + onset + 3.0 * incidence


def one_epoch(model, loader, graph, optimizer, device, weights):
    training = optimizer is not None
    model.train(training)
    cumulative, count = 0., 0
    for x, y, _ in loader:
        x = x.to(device=device, dtype=torch.float32)
        y = y.to(device=device, dtype=torch.float32)
        ensure(torch.isfinite(x).all().item() and torch.isfinite(y).all().item(), 'Nonfinite sequence inputs or targets')
        if training:
            optimizer.zero_grad(set_to_none=True)
        with torch.set_grad_enabled(training):
            predicted = model(x, graph)
            loss = multitask_loss(predicted, y, weights)
            if training:
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 2.0)
                optimizer.step()
        cumulative += float(loss.item()) * len(x)
        count += len(x)
    return cumulative / max(count, 1)


def evaluate_validation(model, loader, disease_names, graph, device):
    model.eval()
    predicted, ground, diseases = [], [], []
    with torch.inference_mode():
        for x, y, disease in loader:
            raw = model(x.to(device=device, dtype=torch.float32), graph)
            decoded = decode_graph_outputs(raw)
            predicted.append(decoded.cpu().numpy())
            ground.append(y.numpy())
            diseases.append(disease.numpy())
    pred = np.concatenate(predicted, axis=0)
    true = np.concatenate(ground, axis=0)
    labels = np.concatenate(diseases)
    metrics = []
    for disease_idx, disease_name in enumerate(disease_names):
        mask = labels == disease_idx
        ensure(mask.any(), f'No validation rows for {disease_name}')
        for d in range(7):
            # Each sample includes ALL 16 blocks. Flatten across blocks.
            p = pred[mask, :, d, :].reshape(-1, 3)
            y = true[mask, :, d, :].reshape(-1, 3)
            metrics.append({
                'disease': disease_name, 'day': d + 1, 'records': int(len(p)),
                'activity_macro_f1': float(f1_score(y[:, 0] >= 0.5, p[:, 0] >= 0.5, labels=[False, True], average='macro', zero_division=0)),
                'new_onset_macro_f1': float(f1_score(y[:, 2] >= 0.5, p[:, 2] >= 0.5, labels=[False, True], average='macro', zero_division=0)),
                'incidence_mae': float(mean_absolute_error(y[:, 1], p[:, 1])),
            })
    return metrics


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode', choices=('smoke', 'full'), default='smoke')
    p.add_argument('--epochs', type=int, default=None)
    p.add_argument('--batch-size', type=int, default=16)
    p.add_argument('--device', choices=('cpu', 'cuda'), default='cpu')
    p.add_argument('--threads', type=int, default=2)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--root', type=Path, help='Optional Component01 folder; normally inferred')
    args = p.parse_args()
    ensure(1 <= args.batch_size <= 512, 'Batch size outside supported range')
    ensure(1 <= args.threads <= 32, 'Threads outside supported range')
    if args.device == 'cuda':
        ensure(torch.cuda.is_available(), 'CUDA requested but not available')
    torch.set_num_threads(args.threads)
    random.seed(args.seed); np.random.seed(args.seed); torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
    root = (args.root or Path(__file__).resolve().parents[2]).resolve()
    train = GraphSequenceDataset(root, 'train', args.mode, args.seed)
    val = GraphSequenceDataset(root, 'validation', args.mode, args.seed)
    ensure(train.bundle['contract'] == val.bundle['contract'], 'Train/validation contracts differ')
    adj_np = np.asarray(train.bundle['adjacency_normalized'], dtype=np.float32)
    ensure(np.allclose(adj_np, val.bundle['adjacency_normalized']), 'Graph differs by split')
    ensure(np.allclose(adj_np, adj_np.T) and np.isfinite(adj_np).all(), 'Adjacency invalid')
    adjacency = torch.from_numpy(adj_np).to(args.device)
    train_loader = DataLoader(train, batch_size=args.batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val, batch_size=args.batch_size, shuffle=False, num_workers=0)
    weights = class_weights_from_train(train).to(args.device)
    cfg = {'n_features': 48, 'graph_hidden': 32, 'lstm_hidden': 48, 'n_nodes': 16}
    model = GraphTemporalForecast(**cfg).to(args.device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.001, weight_decay=0.0001)
    epochs = args.epochs if args.epochs is not None else (1 if args.mode == 'smoke' else 12)
    ensure(1 <= epochs <= 100, 'Epoch count invalid')
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    model_dir = root / 'models/spread/multidisease_step30' / f'{args.mode}_{stamp}'
    report_dir = root / 'outputs/reports/multidisease_step30' / f'{args.mode}_{stamp}'
    model_dir.mkdir(parents=True, exist_ok=False); report_dir.mkdir(parents=True, exist_ok=False)
    best, stale, history = float('inf'), 0, []
    started = time.monotonic()
    print('=' * 76, flush=True)
    print(f'STEP 30 - GRAPH CONVOLUTION + LSTM | {args.mode.upper()} | SIMULATION', flush=True)
    print('=' * 76, flush=True)
    print(f'train_graph_windows={len(train)} validation_graph_windows={len(val)} blocks=16 edges=48', flush=True)
    print('lookback=14 horizon=7 features=48; selection=validation only; TEST NOT LOADED', flush=True)
    for epoch in range(1, epochs + 1):
        loss_train = one_epoch(model, train_loader, adjacency, optimizer, args.device, weights)
        loss_val = one_epoch(model, val_loader, adjacency, None, args.device, weights)
        if loss_val < best - 1e-5:
            best, stale = loss_val, 0
            torch.save({'state_dict': model.state_dict()}, model_dir / 'best_gcn_lstm_weights.pt')
        else:
            stale += 1
        history.append({'epoch': epoch, 'train_loss': loss_train, 'validation_loss': loss_val})
        print(f'epoch {epoch:02}/{epochs} train_loss={loss_train:.5f} val_loss={loss_val:.5f} best_val={best:.5f}', flush=True)
        if args.mode == 'full' and stale >= 3:
            print('Early stopping: no validation improvement for 3 epochs', flush=True)
            break
    state = torch.load(model_dir / 'best_gcn_lstm_weights.pt', map_location=args.device, weights_only=True)
    model.load_state_dict(state['state_dict'])
    disease_names = train.bundle['contract']['disease_names']
    rows = evaluate_validation(model, val_loader, disease_names, adjacency, args.device)
    ensure(len(rows) == 28, 'Expected 4 diseases x 7 validation rows')
    with (report_dir / 'validation_metrics_by_disease_and_day.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    with (report_dir / 'training_history.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(history[0]))
        writer.writeheader(); writer.writerows(history)
    contract = train.bundle['contract']
    manifest = {
        'schema_version': 'step30-v1', 'scope': 'SIMULATION_ONLY_4_DISEASES',
        'model_type': 'GCN_LSTM_16_BLOCK', 'checkpoint': 'best_gcn_lstm_weights.pt',
        'architecture': cfg, 'feature_columns': contract['input_feature_columns'],
        'disease_names': disease_names, 'block_ids': contract['block_ids'],
        'adjacency_sha256': adjacency_sha256(adj_np), 'lookback_days': 14,
        'forecast_days': 7, 'sequence_contract': 'data/processed/multidisease_sequence_graph_contract.json',
        'preprocessing_contract': 'data/processed/multidisease_feature_contract.json',
        'preprocessor': 'data/processed/multidisease_step26_feature_pipeline.joblib',
        'pos_weights_training_only': [float(v) for v in weights.cpu().tolist()],
        'validation_best_loss': float(best), 'epochs_completed': len(history),
        'samples': {'train_graph_windows': len(train), 'validation_graph_windows': len(val)},
        'selection_basis': 'validation_multitask_loss_only', 'test_evaluated': False,
        'real_world_validation': False,
        'notes': 'Synthetic observations, dummy estate adjacency, unverified climate geography. Requires source-ordered train-scaled features.',
    }
    save_json(model_dir / 'manifest.json', manifest)
    save_json(report_dir / 'step30_summary.json', {
        'status': 'PASS_GCN_LSTM_TRAINING', 'model_dir': str(model_dir),
        'validation_best_loss': float(best), 'validation_metric_rows': len(rows),
        'test_evaluated': False, 'elapsed_seconds': round(time.monotonic()-started, 2),
    })
    print('PASS: checkpoint saved; 28 disease/day validation metric rows; TEST NOT USED', flush=True)
    print('Model:', model_dir, flush=True)
    print('Reports:', report_dir, flush=True)
    print('WARNING: synthetic estate graph and disease labels; not real-world validated', flush=True)


if __name__ == '__main__':
    main()
