
import json
import warnings

import joblib
import numpy as np
import pandas as pd

from catboost import CatBoostRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

warnings.filterwarnings("ignore")

from ml.utils.component02.expected_yield_prediction.paths import (
    PROCESSED_DATA_DIR,
    TEST_ROOT,
    model_dir,
)

DATA_DIR = PROCESSED_DATA_DIR
OUTPUT_DIR = TEST_ROOT / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET = "kg_per_Acre"

FEATURES = [
    "Year", "Month_Number", "Week_Number",
    "Temperature", "Rainfall_mm", "Humidity",
    "Wind_Speed", "Solar_Radiation",
    "Location", "Grown_Type",
]

MODEL_PATHS = {
    "Random Forest": model_dir("random_forest") / "random_forest_yield.joblib",
    "XGBoost": model_dir("xgboost") / "xgboost_yield.joblib",
    "LightGBM": model_dir("lightgbm") / "lightgbm_yield.joblib",
    "NGBoost": model_dir("ngboost") / "ngboost_yield.joblib",
    "Extra Trees": model_dir("extra_trees") / "extra_trees_yield.joblib",
    "HistGradientBoosting": model_dir("hist_gradient_boosting") / "hist_gradient_boosting_yield.joblib",
    "CatBoost": model_dir("catboost") / "catboost_yield.cbm",
}

test_df = pd.read_csv(DATA_DIR / "test.csv")

missing = set(FEATURES + [TARGET]) - set(test_df.columns)
if missing:
    raise ValueError(f"test.csv missing columns: {sorted(missing)}")

X_test = test_df[FEATURES]
y_test = test_df[TARGET].astype(float).to_numpy()

all_results = []

print("=" * 65)
print("LOCATION-WISE MODEL EVALUATION - 2025 TEST DATA")
print("=" * 65)

for name, path in MODEL_PATHS.items():
    if not path.exists():
        print(f"SKIPPED {name}: model not found")
        continue

    try:
        if name == "CatBoost":
            model = CatBoostRegressor()
            model.load_model(str(path))
            predictions = model.predict(X_test)
        else:
            saved = joblib.load(path)

            # NGBoost artifact is a dictionary containing
            # the fitted preprocessor and the NGBoost model.
            if isinstance(saved, dict):
                model = saved["model"]
                preprocessor = saved["preprocessor"]
                X_processed = preprocessor.transform(X_test)
                predictions = model.predict(X_processed)
            else:
                predictions = saved.predict(X_test)

        predictions = np.asarray(predictions).reshape(-1)

        if len(predictions) != len(y_test):
            raise ValueError("Prediction count mismatch")

        result_df = test_df[
            ["Year", "Month_Number", "Week_Number", "Location", TARGET]
        ].copy()
        result_df["Predicted_kg_per_Acre"] = predictions
        result_df["Absolute_Error"] = np.abs(y_test - predictions)

        for location, group in result_df.groupby("Location"):
            actual = group[TARGET].to_numpy()
            predicted = group["Predicted_kg_per_Acre"].to_numpy()

            all_results.append({
                "Model": name,
                "Location": location,
                "Rows": len(group),
                "MAE": float(mean_absolute_error(actual, predicted)),
                "RMSE": float(np.sqrt(mean_squared_error(actual, predicted))),
                "R2": float(r2_score(actual, predicted)),
                "MAPE_percent": float(
                    np.mean(np.abs((actual - predicted) / actual)) * 100
                ) if np.all(actual != 0) else None,
            })

        print(f"Evaluated: {name}")

    except Exception as exc:
        print(f"FAILED {name}: {exc}")

if not all_results:
    raise RuntimeError("No models were successfully evaluated.")

results_df = pd.DataFrame(all_results)
results_df.to_csv(
    OUTPUT_DIR / "location_wise_test_metrics_2025.csv",
    index=False,
)

summary = (
    results_df.groupby("Model")
    .agg(
        Mean_Location_MAE=("MAE", "mean"),
        Mean_Location_RMSE=("RMSE", "mean"),
        Mean_Location_R2=("R2", "mean"),
        Locations_Evaluated=("Location", "nunique"),
    )
    .sort_values("Mean_Location_MAE")
    .reset_index()
)

summary.to_csv(
    OUTPUT_DIR / "location_wise_model_summary_2025.csv",
    index=False,
)

print("\n=== LOCATION-WISE MODEL SUMMARY ===")
print(summary.to_string(index=False))

print("\nSaved:")
print(OUTPUT_DIR / "location_wise_test_metrics_2025.csv")
print(OUTPUT_DIR / "location_wise_model_summary_2025.csv")

print("\nEvaluation complete. No model was trained or tuned.")

