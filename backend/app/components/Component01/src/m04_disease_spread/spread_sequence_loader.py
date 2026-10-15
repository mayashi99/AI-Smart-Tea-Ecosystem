"""Reusable Step 27 loader for LSTM / GCN-LSTM synthetic four-disease sequences.

No preprocessing is fitted in this loader. Saved tensors already use train-only scaling.
"""
from pathlib import Path
import json
import numpy as np


def load_bundle(component_root, split):
    if split not in {"train", "validation", "test"}:
        raise ValueError("Split must be train, validation or test")
    processed = Path(component_root) / "data" / "processed"
    contract = json.loads((processed / "multidisease_sequence_graph_contract.json").read_text(encoding="utf-8"))
    with np.load(processed / f"multidisease_sequence_graph_{split}.npz", allow_pickle=False) as src:
        tensors = {name: src[name] for name in ("X_days", "Y_days", "sample_indices", "dates")}
    with np.load(processed / "multidisease_graph_adjacency.npz", allow_pickle=False) as src:
        adjacency = src["adjacency_normalized"]
        block_ids = [str(item) for item in src["block_ids"]]
    if block_ids != contract["block_ids"]:
        raise ValueError("Adjacency block ordering differs from sequence contract")
    length = int(contract["sequence_days"])
    x, y, ix = tensors["X_days"], tensors["Y_days"], tensors["sample_indices"]
    if x.ndim != 4 or x.shape[1:] != (4, 16, 48):
        raise ValueError(f"Unexpected X_days shape: {x.shape}")
    if y.shape != (len(x), 4, 16, 7, 3):
        raise ValueError(f"Unexpected Y_days shape: {y.shape}")
    if ix.shape != ((len(x)-length+1)*4, 2):
        raise ValueError(f"Unexpected sequence index shape: {ix.shape}")
    if adjacency.shape != (16, 16):
        raise ValueError("Unexpected adjacency matrix shape")
    return {**tensors, "adjacency_normalized": adjacency, "contract": contract}


def extract_sample(bundle, sample_number, block_index=None):
    """Return (X_window, Y_label, norm_adj, origin) with no future inputs.

    block_index=None (GCN-LSTM): X [lookback,16,48], Y [16,7,3]
    block_index=0..15 (per-block LSTM): X [lookback,48], Y [7,3]
    """
    end, disease_idx = map(int, bundle["sample_indices"][sample_number])
    length = int(bundle["contract"]["sequence_days"])
    if end < length-1:
        raise ValueError("Insufficient historical dates for this sample")
    x = bundle["X_days"][end-length+1:end+1, disease_idx]
    y = bundle["Y_days"][end, disease_idx]
    if block_index is not None:
        if not 0 <= block_index < 16:
            raise ValueError("Invalid block index")
        x, y = x[:, block_index, :], y[block_index]
    return x, y, bundle["adjacency_normalized"], str(bundle["dates"][end])


class SpreadSequenceDataset:
    """Simple PyTorch Dataset for GCN-LSTM or per-block LSTM.

    Need torch installed to instantiate. For per-block model, each block is a sample,
    indexed as sequence_id * 16 + block_index. For graph model, each sample contains
    all 16 blocks.
    """
    def __init__(self, component_root, split, mode="graph"):
        if mode not in {"graph", "block"}:
            raise ValueError("mode must be 'graph' or 'block'")
        self.bundle = load_bundle(component_root, split)
        self.mode = mode

    def __len__(self):
        samples = len(self.bundle["sample_indices"])
        return samples if self.mode == "graph" else samples * 16

    def __getitem__(self, index):
        import torch
        if self.mode == "graph":
            x, y, _, _ = extract_sample(self.bundle, index)
        else:
            seq_id, block_index = divmod(index, 16)
            x, y, _, _ = extract_sample(self.bundle, seq_id, block_index)
        return torch.from_numpy(np.ascontiguousarray(x)), torch.from_numpy(np.ascontiguousarray(y))
