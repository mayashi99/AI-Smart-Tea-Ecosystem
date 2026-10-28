# Backend ML layout

Component-specific pipelines follow the same lifecycle-oriented structure:

- `datasets/raw/<component>/<pipeline>`: source datasets.
- `datasets/processed/<component>/<pipeline>`: reproducible train/validation/test splits.
- `preprocessing/<component>/<pipeline>`: validation and data preparation.
- `feature_engineering/<component>/<pipeline>`: shared feature schemas and transformations.
- `training/<component>/<pipeline>/<algorithm>`: training, tuning, and evaluation programs.
- `models/<component>/<pipeline>/<algorithm>`: inference module, trained artifacts, and evaluation outputs.
- `tests/<component>/<pipeline>`: cross-model evaluation and regression tests.
- `utils/<component>/<pipeline>`: reusable pipeline utilities used by the API.

Run modules from `backend`, for example:

```bash
python -m ml.preprocessing.component02.expected_yield_prediction.split_dataset
python -m ml.training.component02.expected_yield_prediction.catboost.catboost_train
```

The FastAPI layer remains under `app/` and imports inference utilities from `ml/`.
