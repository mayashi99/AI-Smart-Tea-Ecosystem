# Backend deep-learning layout

Component 02 image pipelines are organized by lifecycle:

- `datasets/raw/component02/<pipeline>`: original source images.
- `datasets/processed/component02/<pipeline>`: training and validation splits.
- `datasets/tests/component02/<pipeline>`: held-out test images.
- `preprocessing/component02/<pipeline>`: splitting and leakage checks.
- `training/component02/<pipeline>/<architecture>`: training and evaluation programs.
- `models/component02/<pipeline>/<architecture>`: inference modules, weights, runs, and evaluation artifacts.
- `tests/component02/<pipeline>`: deep-learning regression tests.
- `utils/component02/paths.py`: canonical paths shared by APIs and training code.

Run modules from `backend`, for example:

```bash
python -m DL.preprocessing.component02.harvest_readiness.split_dataset
python -m DL.training.component02.harvest_readiness.yolo11.train_model
python -m DL.preprocessing.component02.plantation_health.split_dataset
python -m DL.training.component02.plantation_health.yolo11.train
python -m DL.models.component02.plantation_health.yolo11.predict /path/to/image.jpg
```

FastAPI routing and climate-service logic remain under `app/`; model-specific code and artifacts live here.
