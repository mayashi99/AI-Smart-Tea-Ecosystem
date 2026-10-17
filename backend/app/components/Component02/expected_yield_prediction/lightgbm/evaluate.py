"""Evaluate saved LightGBM weights on the 2025 test split without retraining."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

if __package__:
    from .predict import BASE_DIR, MODEL_PATH, load_model, prepare_features
else:
    from predict import BASE_DIR, MODEL_PATH, load_model, prepare_features

TEST_PATH = BASE_DIR.parent / "data" / "splits" / "test.csv"
OUTPUT_DIR = BASE_DIR / "outputs"
TARGET = "kg_per_Acre"


def evaluate(test_path=TEST_PATH, model_path=MODEL_PATH, output_dir=OUTPUT_DIR):
    """Write test metrics and row-level errors; preserve validation artifacts."""
    frame = pd.read_csv(test_path)
    if TARGET not in frame:
        raise ValueError(f"Test data is missing target column: {TARGET}")
    features = prepare_features(frame)
    if not (features.Year == 2025).all():
        raise ValueError("Expected only held-out 2025 test rows.")
    actual = pd.to_numeric(frame[TARGET], errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(actual).all() or (actual < 0).any():
        raise ValueError("Test targets must be finite, nonnegative yields.")
    # Predict with the saved pipeline; never fit preprocessing on the test set.
    predicted = np.asarray(load_model(model_path).predict(features), dtype=float).reshape(-1)
    if predicted.shape != actual.shape or not np.isfinite(predicted).all():
        raise ValueError("Model predictions must be finite and match the test row count.")
    nonzero = actual != 0
    metrics = {
        "model": "LightGBM", "target": TARGET, "test_year": 2025,
        "test_rows": len(frame),
        "MAE": float(mean_absolute_error(actual, predicted)),
        "RMSE": float(np.sqrt(mean_squared_error(actual, predicted))),
        "R2": float(r2_score(actual, predicted)) if len(actual) > 1 else None,
        # Zero actuals have undefined percentage errors; serialize unavailable MAPE as null.
        "MAPE_percent": float(np.mean(np.abs((actual[nonzero] - predicted[nonzero]) / actual[nonzero])) * 100) if nonzero.any() else None,
    }
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    results = frame[["Year", "Month_Number", "Week_Number", "Location", "Grown_Type", TARGET]].copy()
    results["Predicted_kg_per_Acre"] = predicted
    results["Absolute_Error"] = np.abs(actual - predicted)
    results.to_csv(output / "test_predictions_2025.csv", index=False)
    with (output / "test_metrics_2025.json").open("w", encoding="utf-8") as target:
        json.dump(metrics, target, indent=4, allow_nan=False)
    return metrics


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=4, allow_nan=False))
