"""Step 30 graph-temporal inference for SYNTHETIC four-disease/16-block estate.

Input must already use Step 26 TRAIN-fitted preprocessing/scaling, in the
Step 27 feature, disease and block ordering. Never use arbitrary raw CSV arrays.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

import numpy as np
import torch
from torch import nn


class GraphTemporalForecast(nn.Module):
    """Two adjacency-weighted graph layers per day, then shared node-wise LSTM.

    X: [batch, 14 days, 16 blocks, 48 features]
    A: [16,16], Step 27 normalized and self-looped
    output logits: [batch,16 blocks,7 horizons,3 heads]
    """
    def __init__(self, n_features=48, graph_hidden=32, lstm_hidden=48, n_nodes=16):
        super().__init__()
        self.n_nodes = n_nodes
        self.n_features = n_features
        self.graph1 = nn.Linear(n_features, graph_hidden)
        self.norm1 = nn.LayerNorm(graph_hidden)
        self.graph2 = nn.Linear(graph_hidden, graph_hidden)
        self.norm2 = nn.LayerNorm(graph_hidden)
        self.temporal = nn.LSTM(graph_hidden, lstm_hidden, batch_first=True)
        self.head = nn.Sequential(nn.LayerNorm(lstm_hidden), nn.Linear(lstm_hidden, 7 * 3))

    def forward(self, x, adjacency):
        if x.ndim != 4 or x.shape[2:] != (self.n_nodes, self.n_features):
            raise ValueError(f'Expected [B,T,{self.n_nodes},{self.n_features}], got {tuple(x.shape)}')
        if adjacency.shape != (self.n_nodes, self.n_nodes):
            raise ValueError('Incorrect adjacency dimensions')
        # Real graph propagation on every timestep, including neighboring blocks.
        h = torch.einsum('ij,btjf->btif', adjacency, x)
        h = torch.relu(self.norm1(self.graph1(h)))
        h = torch.einsum('ij,btjf->btif', adjacency, h)
        h = torch.relu(self.norm2(self.graph2(h)))
        batch, days, nodes, hidden = h.shape
        h = h.permute(0, 2, 1, 3).contiguous().reshape(batch * nodes, days, hidden)
        _, (last, _) = self.temporal(h)
        raw = self.head(last[-1]).reshape(batch, nodes, 7, 3)
        return raw


def decode_graph_outputs(logits):
    decoded = logits.clone()
    decoded[..., 0] = torch.sigmoid(logits[..., 0])
    decoded[..., 1] = torch.sigmoid(logits[..., 1]) * 100.0
    decoded[..., 2] = torch.sigmoid(logits[..., 2])
    return decoded


def adjacency_sha256(adjacency):
    arr = np.ascontiguousarray(np.asarray(adjacency, dtype=np.float32))
    return hashlib.sha256(arr.tobytes()).hexdigest()


def load_gcn_lstm(run_dir, component_root=None, device='cpu'):
    run_dir = Path(run_dir).resolve()
    manifest = json.loads((run_dir / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('model_type') != 'GCN_LSTM_16_BLOCK' or manifest.get('scope') != 'SIMULATION_ONLY_4_DISEASES':
        raise ValueError('Unsupported model manifest/scope')
    if component_root is None:
        # .../Component01/models/spread/multidisease_step30/full_<timestamp>
        component_root = run_dir.parents[3]
    component_root = Path(component_root).resolve()
    contract = json.loads((component_root / manifest['sequence_contract']).read_text(encoding='utf-8'))
    if contract['block_ids'] != manifest['block_ids'] or contract['disease_names'] != manifest['disease_names']:
        raise ValueError('Model/data contract mismatch')
    if contract['input_feature_columns'] != manifest['feature_columns']:
        raise ValueError('Training feature order changed')
    with np.load(component_root / 'data/processed/multidisease_graph_adjacency.npz', allow_pickle=False) as data:
        adjacency = data['adjacency_normalized'].astype(np.float32)
        block_ids = [str(v) for v in data['block_ids']]
    if block_ids != manifest['block_ids'] or adjacency_sha256(adjacency) != manifest['adjacency_sha256']:
        raise ValueError('Graph node order or adjacency has changed')
    model = GraphTemporalForecast(**manifest['architecture']).to(device)
    checkpoint = torch.load(run_dir / manifest['checkpoint'], map_location=device, weights_only=True)
    model.load_state_dict(checkpoint['state_dict'], strict=True)
    model.eval()
    return model, torch.from_numpy(adjacency).to(device), manifest


def predict_scaled_graph_window(run_dir, pre_scaled_history, disease_name, component_root=None, device='cpu'):
    model, adjacency, manifest = load_gcn_lstm(run_dir, component_root=component_root, device=device)
    if disease_name not in manifest['disease_names']:
        raise ValueError(f'Unknown disease: {disease_name}')
    arr = np.asarray(pre_scaled_history, dtype=np.float32)
    expected = (manifest['lookback_days'], len(manifest['block_ids']), len(manifest['feature_columns']))
    if arr.shape != expected or not np.isfinite(arr).all():
        raise ValueError(f'Expected finite, pre-scaled window {expected}; got {arr.shape}')
    with torch.inference_mode():
        inp = torch.from_numpy(np.ascontiguousarray(arr)).unsqueeze(0).to(device)
        preds = decode_graph_outputs(model(inp, adjacency))[0].cpu().numpy()
    return {
        'disease': disease_name,
        'forecast_by_block': {
            block: [{
                'day': day + 1,
                'disease_active_probability': float(preds[j, day, 0]),
                'incidence_percent': float(preds[j, day, 1]),
                'new_onset_probability': float(preds[j, day, 2]),
            } for day in range(7)] for j, block in enumerate(manifest['block_ids'])
        },
        'data_provenance': 'SIMULATION_ONLY_NOT_FIELD_VALIDATED',
        'note': 'Uncalibrated probabilities; requires Step26 scaling, exact feature/block order and historical availability',
    }
