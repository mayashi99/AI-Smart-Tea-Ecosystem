"""Evaluate the saved SARIMAX location models on the held-out test split."""

import json
from pathlib import Path

if __package__:
    from .predict import predict_rows
else:
    from predict import predict_rows
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR.parent / "data" / "splits" / "test.csv"
OUTPUT_DIR = BASE_DIR / "outputs"
TARGET = "kg_per_Acre"
FEATURES = ["Year", "Month_Number", "Week_Number", "Location"]


def main():
    test_df = pd.read_csv(DATA_PATH)
    missing = set(FEATURES + [TARGET]) - set(test_df.columns)
    if missing:
        raise ValueError(f"test.csv missing columns: {sorted(missing)}")
    if len(test_df) < 2:
        raise ValueError("test.csv needs at least two rows to calculate R2.")

    actual = pd.to_numeric(test_df[TARGET], errors="raise").to_numpy(dtype=float)
    if not np.isfinite(actual).all():
        raise ValueError("Test targets must be finite numbers without missing values.")

    # Forecast across the validation-year gap without observing its targets.
    predictions = predict_rows(test_df[FEATURES])
    if predictions.shape != actual.shape or not np.isfinite(predictions).all():
        raise ValueError("Model must return one finite prediction per test row.")

    nonzero = actual != 0
    mape = (
        float(np.mean(np.abs((actual[nonzero] - predictions[nonzero]) / actual[nonzero])) * 100)
        if nonzero.any() else None
    )
    metrics = {
        "model": "SARIMAX",
        "target": TARGET,
        "forecast_policy": "Fixed training origin; no validation/test target updates; 48 periods per year",
        "test_years": sorted(test_df["Year"].unique().tolist()),
        "test_rows": len(test_df),
        "MAE": float(mean_absolute_error(actual, predictions)),
        "RMSE": float(np.sqrt(mean_squared_error(actual, predictions))),
        "R2": float(r2_score(actual, predictions)),
        "MAPE_percent": mape,
        "MAPE_excluded_zero_targets": int((~nonzero).sum()),
    }

    results = test_df[["Year", "Month_Number", "Week_Number", "Location", TARGET]].copy()
    results["Predicted_kg_per_Acre"] = predictions
    results["Absolute_Error"] = np.abs(actual - predictions)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metrics_path = OUTPUT_DIR / "test_metrics.json"
    predictions_path = OUTPUT_DIR / "test_predictions.csv"
    metrics_path.write_text(json.dumps(metrics, indent=4, allow_nan=False) + "\n", encoding="utf-8")
    results.to_csv(predictions_path, index=False)

    print("=== SARIMAX TEST EVALUATION ===")
    print(f"Test years: {metrics['test_years']} | Rows: {len(test_df)}")
    for name in ("MAE", "RMSE", "R2"):
        print(f"{name}: {metrics[name]:.4f}")
    print(f"MAPE: {mape:.2f}%" if mape is not None else "MAPE: undefined (all targets are zero)")
    print(f"MAPE excluded zero targets: {metrics['MAPE_excluded_zero_targets']}")
    print(f"Metrics saved: {metrics_path}")
    print(f"Predictions saved: {predictions_path}")
    print("Evaluation complete. No training or tuning performed.")


if __name__ == "__main__":
    main()
