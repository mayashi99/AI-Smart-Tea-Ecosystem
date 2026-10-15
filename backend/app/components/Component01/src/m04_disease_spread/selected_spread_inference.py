"""Step 32 selected-family four-disease 7-day simulation inference.

Contract: input is already Step26-engineered 48 raw tabular columns for the
forecast origin and Step27 TRAIN-scaled 14-day historical window for all 16
blocks. Never pass unprocessed live observations or raw weather data.

This runtime is intended for later FastAPI services, but does not itself
implement observation preprocessing, temporal feature updating, or a live API.
All predictions are synthetic-prototype outputs; probabilities UNCALIBRATED.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd
import torch

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from multidisease_lstm_inference import decode_predictions, load_lstm
from multidisease_gcn_lstm_inference import decode_graph_outputs, load_gcn_lstm

KINDS = ('Disease_Active', 'Incidence_Pct', 'New_Onset_By')
ALLOWED_FAMILIES = {'ml_winners', 'lstm', 'gcn_lstm'}
SCOPE = 'SIMULATION_ONLY_NOT_FIELD_VALIDATED'


def require(condition: bool, message: str):
    if not condition:
        raise ValueError(message)


def json_from(path: Path) -> dict:
    require(path.is_file(), f'Missing artifact: {path}')
    return json.loads(path.read_text(encoding='utf-8'))


def under(root: Path, path: str) -> Path:
    """Reject absolute or escaping paths in manifest references."""
    candidate = (root / path).resolve()
    require(candidate.is_relative_to(root), f'Checkpoint path outside Component01: {path}')
    return candidate


class SelectedSpreadPredictor:
    def __init__(self, component_root, device='cpu', threads=2):
        self.root = Path(component_root).resolve()
        require(device == 'cpu', 'Step32 supports CPU only')
        require(1 <= threads <= 16, 'threads must be 1-16')
        torch.set_num_threads(threads)
        model_root = self.root / 'models/spread'
        self.selection = json_from(model_root / 'multidisease_step31/validation_selected_families.json')
        require(self.selection.get('mode') == 'full' and
                self.selection.get('schema_version') == 'step31-v1' and
                self.selection.get('status') == 'PASS_VALIDATION_ALIGNED_COMPARISON',
                'Requires Step31 FULL comparison, not a smoke/partial selection')
        require(not self.selection.get('test_dataset_accessed', True), 'Selection used test data')
        self.family_choice = {r['target']: r['selected_family'] for r in self.selection['selected_families']}
        wanted = {f'Target_{kind}_Day_{day}' for day in range(1,8) for kind in KINDS}
        require(len(self.selection['selected_families']) == 21 and
                set(self.family_choice) == wanted and
                set(self.family_choice.values()) <= ALLOWED_FAMILIES,
                'Selection must have exactly 21 valid model family entries')
        self.seq_contract = json_from(self.root / 'data/processed/multidisease_sequence_graph_contract.json')
        self.feature_contract = json_from(self.root / 'data/processed/multidisease_feature_contract.json')
        self.features = list(self.feature_contract['feature_columns'])
        self.diseases = list(self.seq_contract['disease_names'])
        self.blocks = list(self.seq_contract['block_ids'])
        require(self.features == self.seq_contract['input_feature_columns'], 'Step26/27 feature mismatch')
        require(len(self.features)==48 and len(self.diseases)==4 and len(self.blocks)==16,
                'Expected 48 features, four diseases, 16 blocks')
        require(self.seq_contract['sequence_days']==14, 'Expected 14 historical days')
        require(not any(name.startswith('Target_') for name in self.features),
                'Future target leaked into feature list')
        self.run_dirs = {
            family: under(self.root, self.selection['family_runs'][family])
            for family in ALLOWED_FAMILIES
        }
        self.ml_manifest = json_from(self.run_dirs['ml_winners'] / 'manifest.json')
        require(self.ml_manifest.get('mode')=='full' and self.ml_manifest.get('model_count')==21,
                'Step28 full ML winners missing')
        require(self.ml_manifest['feature_columns']==self.features, 'Step28 feature order mismatch')
        require(self.ml_manifest['disease_names']==self.diseases, 'Step28 disease order mismatch')
        self.ml_choices = {r['target']:r for r in self.ml_manifest['chosen']}
        require(set(self.ml_choices)==wanted, 'Step28 ML target choice mismatch')
        self._ml_cache = {}
        self._lstm = None
        self._gcn = None

    def _load_ml(self, target):
        if target not in self._ml_cache:
            ckpt = under(self.run_dirs['ml_winners'], self.ml_choices[target]['checkpoint'])
            require(ckpt.is_file(), f'Missing ML estimator for {target}: {ckpt}')
            self._ml_cache[target] = joblib.load(ckpt)  # project-generated trusted artifacts only
        return self._ml_cache[target]

    def _ml_predict(self, target, tabular):
        estimator = self._load_ml(target)
        inputs = tabular
        if estimator.__class__.__module__.startswith('lightgbm'):
            names = getattr(estimator, 'feature_names_in_', None)
            if names is not None and len(names)==len(self.features):
                inputs = pd.DataFrame(tabular, columns=[str(x) for x in names])
        pred = np.asarray(estimator.predict(inputs), dtype=np.float64)
        require(pred.shape == (16,) and np.isfinite(pred).all(), f'Invalid ML result: {target}')
        if 'Incidence_Pct' in target:
            return np.clip(pred, 0, 100), None
        require(np.isin(pred, [0,1]).all(), f'Nonbinary ML result: {target}')
        prob = None
        if hasattr(estimator, 'predict_proba'):
            classes = list(getattr(estimator, 'classes_', []))
            if 1 in classes:
                prob_raw = np.asarray(estimator.predict_proba(inputs), dtype=np.float64)
                prob = prob_raw[:, classes.index(1)]
                require(prob.shape==(16,) and np.isfinite(prob).all(),
                        f'Bad uncalibrated ML probabilities: {target}')
                prob = np.clip(prob, 0, 1)
        return pred.astype(np.int32), prob

    def predict_disease(self, disease_name: str, history_scaled, tabular_origin):
        """Return 16 block x 7 day forecasts from preprocessed arrays.

        history_scaled: [14,16,48] from Step27 scaler, oldest -> latest.
        tabular_origin: [16,48] Step26 unscaled engineered features at origin.
        Caller must ensure same origin date, disease, block ordering and provenance.
        """
        require(disease_name in self.diseases, f'Unsupported disease {disease_name!r}')
        history = np.asarray(history_scaled, dtype=np.float32)
        tabular = np.asarray(tabular_origin, dtype=np.float32)
        require(history.shape==(14,16,48) and tabular.shape==(16,48),
                f'Expected history (14,16,48), tabular (16,48); got {history.shape}, {tabular.shape}')
        require(np.isfinite(history).all() and np.isfinite(tabular).all(),
                'Nonfinite model input')
        used = set(self.family_choice.values())
        deep = {}
        if 'lstm' in used:
            if self._lstm is None:
                self._lstm = load_lstm(self.run_dirs['lstm'], device='cpu')
                _,m = self._lstm
                require(m['disease_names']==self.diseases and m['block_ids']==self.blocks
                        and m['lookback_days']==14 and m['feature_count']==48,
                        'LSTM model/data contract mismatch')
            model, _ = self._lstm
            with torch.inference_mode():
                # [T,B,F] -> [B,T,F]
                tensor = torch.from_numpy(np.ascontiguousarray(history.transpose(1,0,2)))
                deep['lstm'] = decode_predictions(model(tensor)).cpu().numpy()
        if 'gcn_lstm' in used:
            if self._gcn is None:
                self._gcn = load_gcn_lstm(self.run_dirs['gcn_lstm'],
                                          component_root=self.root, device='cpu')
                _,_,m = self._gcn
                require(m['disease_names']==self.diseases and m['block_ids']==self.blocks and
                        m['feature_columns']==self.features and m['lookback_days']==14,
                        'GCN model/data contract mismatch')
            model,adj,_ = self._gcn
            with torch.inference_mode():
                tensor = torch.from_numpy(np.ascontiguousarray(history[None]))
                deep['gcn_lstm'] = decode_graph_outputs(model(tensor,adj))[0].cpu().numpy()
        output=[]
        for day in range(1,8):
            per_kind = {}
            for ki,kind in enumerate(KINDS):
                target=f'Target_{kind}_Day_{day}'
                family=self.family_choice[target]
                if family=='ml_winners':
                    scores, probs=self._ml_predict(target, tabular)
                    model_name=self.ml_choices[target]['best_model']
                else:
                    scores=deep[family][:,day-1,ki]
                    probs=None if ki==1 else scores
                    model_name=family
                per_kind[kind] = (family,model_name,scores,probs)
            activity,incidence,onset = (per_kind[k] for k in KINDS)
            for bi,block in enumerate(self.blocks):
                row={
                    'disease_name':disease_name,'block_id':block,'horizon_day':day,
                    'activity_predicted_class': int(activity[2][bi] if activity[0]=='ml_winners' else activity[2][bi]>=0.5),
                    'activity_probability_uncalibrated': None if activity[3] is None else float(activity[3][bi]),
                    'incidence_percent_prediction': float(np.clip(incidence[2][bi],0,100)),
                    'new_onset_predicted_class': int(onset[2][bi] if onset[0]=='ml_winners' else onset[2][bi]>=0.5),
                    'new_onset_probability_uncalibrated': None if onset[3] is None else float(onset[3][bi]),
                    'activity_family': activity[0], 'incidence_family': incidence[0], 'onset_family': onset[0],
                    'activity_model': activity[1], 'incidence_model': incidence[1], 'onset_model': onset[1],
                    'data_provenance':SCOPE,
                }
                output.append(row)
        require(len(output)==16*7, 'Expected 112 block-day records per disease')
        return output
