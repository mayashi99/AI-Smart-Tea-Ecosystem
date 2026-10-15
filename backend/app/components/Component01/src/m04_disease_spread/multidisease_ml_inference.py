"""Step28 saved-model inference for already-engineered 48-column Step26 input.

These models only support simulated demonstration data. Callers creating live
observations must apply Step25+Step26 historical preprocessing first.
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np


class MultiDiseaseBaselinePredictor:
    def __init__(self, manifest_path):
        self.manifest_path = Path(manifest_path).resolve()
        self.manifest = json.loads(self.manifest_path.read_text(encoding='utf-8'))
        if self.manifest.get('schema_version') != 'step28-v1':
            raise ValueError('Incompatible Step28 manifest version')
        self.features = list(self.manifest['feature_columns'])
        self.choices = {row['target']: row for row in self.manifest['chosen']}
        if len(self.features) != 48:
            raise ValueError('Expected 48 precomputed features')
        self._models = {}

    def _model(self, target):
        if target not in self.choices:
            raise KeyError(f'Target unavailable in this checkpoint: {target}')
        if target not in self._models:
            ckpt = (self.manifest_path.parent / self.choices[target]['checkpoint']).resolve()
            if ckpt.parent != self.manifest_path.parent:
                raise ValueError('Unexpected checkpoint path traversal')
            self._models[target] = joblib.load(ckpt)  # use only trusted self-generated files
        return self._models[target]

    def predict(self, feature_row: dict, day: int, kind: str):
        if day not in range(1, 8):
            raise ValueError('Horizon day must be 1-7')
        if kind not in {'Disease_Active', 'Incidence_Pct', 'New_Onset_By'}:
            raise ValueError('Unknown target type')
        target = f'Target_{kind}_Day_{day}'
        if set(feature_row) != set(self.features):
            missing = set(self.features) - set(feature_row)
            extra = set(feature_row) - set(self.features)
            raise ValueError(f'Exact Step26 feature contract required: missing={missing} extra={extra}')
        values = np.array([[float(feature_row[c]) for c in self.features]], dtype='float32')
        if not np.isfinite(values).all():
            raise ValueError('Nonfinite features')
        choice = self.choices.get(target)
        if choice is None:
            raise ValueError(f'{target} not available (smoke checkpoint may contain subset only)')
        model = self._model(target)
        value = float(model.predict(values)[0])
        if choice['task'] == 'classification':
            value = int(round(value))
        else:
            value = float(np.clip(value, 0, 100))
        return {'day': day, 'target': kind, 'prediction': value,
                'selected_model': choice['best_model'],
                'data_provenance': 'SIMULATION_ONLY_NOT_FIELD_VALIDATED'}
