"""Step 29 LSTM architecture + saved checkpoint inference for 4 simulated diseases.

Input is a 14-day window of *already Step-26-train-scaled* 48-feature rows
for one disease and ONE block, ordered oldest to newest. Not raw CSV rows.
"""
from pathlib import Path
import json
import numpy as np
import torch
from torch import nn


class BlockForecastLSTM(nn.Module):
    def __init__(self, input_size=48, hidden_size=48, num_layers=1, dropout=0.0):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers=num_layers,
                            dropout=dropout if num_layers > 1 else 0.0, batch_first=True)
        self.head = nn.Sequential(nn.LayerNorm(hidden_size), nn.Linear(hidden_size, 21))

    def forward(self, sequences):
        # Outputs [batch, 7_days, 3_outputs]. Columns 0 and 2 are binary logits;
        # column 1 is an unconstrained logit for incidence% via sigmoid * 100.
        _, (last_hidden, _) = self.lstm(sequences)
        return self.head(last_hidden[-1]).reshape(-1, 7, 3)


def decode_predictions(raw):
    out = raw.clone()
    out[..., 0] = torch.sigmoid(raw[..., 0])
    out[..., 1] = 100.0 * torch.sigmoid(raw[..., 1])
    out[..., 2] = torch.sigmoid(raw[..., 2])
    return out


def load_lstm(run_dir, device='cpu'):
    run_dir = Path(run_dir)
    manifest = json.loads((run_dir / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('scope') != 'SIMULATION_ONLY_4_DISEASES':
        raise ValueError('Unsupported artifact scope')
    state = torch.load(run_dir / manifest['checkpoint'], map_location=device, weights_only=True)
    cfg = manifest['architecture']
    model = BlockForecastLSTM(**cfg).to(device)
    model.load_state_dict(state['state_dict'], strict=True)
    model.eval()
    return model, manifest


def predict_scaled_block_window(run_dir, pre_scaled_history, device='cpu'):
    model, manifest = load_lstm(run_dir, device=device)
    arr = np.asarray(pre_scaled_history, dtype=np.float32)
    expected = (manifest['lookback_days'], manifest['feature_count'])
    if arr.shape != expected or not np.isfinite(arr).all():
        raise ValueError(f'Expected finite, pre-scaled window {expected}; got {arr.shape}')
    with torch.inference_mode():
        output = decode_predictions(model(torch.from_numpy(arr).unsqueeze(0).to(device)))
    prediction = output[0].cpu().numpy()
    return {
        'forecast_days': [{
            'day': int(i+1),
            'disease_active_probability': float(prediction[i, 0]),
            'incidence_percent': float(prediction[i, 1]),
            'new_onset_probability': float(prediction[i, 2]),
        } for i in range(7)],
        'data_provenance': 'SIMULATION_ONLY_NOT_FIELD_VALIDATED',
        'note': 'Uncalibrated model probabilities; training-time feature scaling is required',
    }
