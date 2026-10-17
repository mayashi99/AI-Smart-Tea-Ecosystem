
from pathlib import Path
import json
import warnings

import joblib
import numpy as np
import pandas as pd

from catboost import CatBoostRegressor
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)

warnings.filterwarnings("ignore")

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "splits"
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET = "kg_per_Acre"

FEATURES = [
    "Year", "Month_Number", "Week_Number",
    "Temperature", "Rainfall_mm", "Humidity",
    "Wind_Speed", "Solar_Radiation",
    "Location", "Grown_Type",
]

test_df = pd.read_csv(DATA_DIR / "test.csv")

missing = set(FEATURES + [TARGET]) - set(test_df.columns)
if missing:
    raise ValueError(f"test.csv missing columns: {sorted(missing)}")

X_test = test_df[FEATURES]
y_test = test_df[TARGET].astype(float).to_numpy()

MODEL_PATHS = {
    "Random Forest": BASE_DIR / "random_forest/models/random_forest_yield.joblib",
    "XGBoost": BASE_DIR / "xgboost/models/xgboost_yield.joblib",
    "LightGBM": BASE_DIR / "lightgbm/models/lightgbm_yield.joblib",
    "NGBoost": BASE_DIR / "ngboost/models/ngboost_yield.joblib",
    "Extra Trees": BASE_DIR / "extra_trees/models/extra_trees_yield.joblib",
    "HistGradientBoosting": BASE_DIR / "hist_gradient_boosting/models/hist_gradient_boosting_yield.joblib",
    "CatBoost": BASE_DIR / "catboost/models/catboost_yield.cbm",
}

def calculate_metrics(actual, predicted):
    nonzero = actual != 0
    mape = (
        np.mean(
            np.abs(
                (actual[nonzero] - predicted[nonzero])
                / actual[nonzero]
            )
        ) * 100
        if nonzero.any()
        else float("nan")
    )

    return {
        "MAE": float(mean_absolute_error(actual, predicted)),
        "RMSE": float(np.sqrt(mean_squared_error(actual, predicted))),
        "R2": float(r2_score(actual, predicted)),
        "MAPE_percent": float(mape),
    }

results = []
prediction_columns = test_df[
    ["Year", "Month_Number", "Week_Number", "Location", TARGET]
].copy()

print("=" * 60)
print("FINAL MODEL COMPARISON - 2025 TEST DATA")
print("=" * 60)
print(f"Test rows: {len(test_df)}")
print(f"Test years: {sorted(test_df['Year'].unique())}")
print("No model will be trained or tuned using this test set.\n")

for name, path in MODEL_PATHS.items():
    if not path.exists():
        print(f"SKIPPED {name}: model file not found: {path}")
        continue

    try:
        if name == "CatBoost":
            model = CatBoostRegressor()
            model.load_model(str(path))
            predictions = model.predict(X_test)

        elif name == "NGBoost":
            artifact = joblib.load(path)

            if not isinstance(artifact, dict):
                raise TypeError("Expected NGBoost artifact to be a dictionary.")

            ngb_model = artifact["model"]
            preprocessor = artifact["preprocessor"]
            feature_columns = artifact["feature_columns"]

            X_ngb = X_test[feature_columns]
            X_ngb_processed = preprocessor.transform(X_ngb)

            predictions = ngb_model.predict(X_ngb_processed)

        else:
            model = joblib.load(path)
            predictions = model.predict(X_test)

        predictions = np.asarray(predictions).reshape(-1)

        if len(predictions) != len(y_test):
            raise ValueError("Prediction count does not match test rows.")

        metrics = calculate_metrics(y_test, predictions)

        results.append({
            "Model": name,
            **metrics,
            "Test_Rows": len(y_test),
        })

        prediction_columns[f"{name}_Prediction"] = predictions

        print(f"{name}:")
        print(f"  MAE:  {metrics['MAE']:.4f}")
        print(f"  RMSE: {metrics['RMSE']:.4f}")
        print(f"  R2:   {metrics['R2']:.4f}")
        print(f"  MAPE: {metrics['MAPE_percent']:.2f}%\n")

    except Exception as exc:
        print(f"FAILED {name}: {exc}\n")

if not results:
    raise RuntimeError("No models were evaluated successfully.")

results_df = pd.DataFrame(results).sort_values(
    "MAE", ascending=True
).reset_index(drop=True)

results_df.to_csv(
    OUTPUT_DIR / "test_model_comparison_2025.csv",
    index=False,
)

prediction_columns.to_csv(
    OUTPUT_DIR / "test_predictions_2025.csv",
    index=False,
)

with open(OUTPUT_DIR / "test_model_comparison_2025.json", "w") as f:
    json.dump(results, f, indent=4)

print("=" * 60)
print("2025 TEST RESULTS")
print("=" * 60)
print(results_df.to_string(index=False))

best = results_df.iloc[0]
print(f"\nBest model by test MAE: {best['Model']}")
print(f"MAE:  {best['MAE']:.4f}")
print(f"RMSE: {best['RMSE']:.4f}")
print(f"R2:   {best['R2']:.4f}")

print("\nSaved files:")
print(OUTPUT_DIR / "test_model_comparison_2025.csv")
print(OUTPUT_DIR / "test_predictions_2025.csv")
print(OUTPUT_DIR / "test_model_comparison_2025.json")
