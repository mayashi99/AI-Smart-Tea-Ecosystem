
import json
import warnings

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

warnings.filterwarnings("ignore")

from ml.utils.component02.expected_yield_prediction.paths import (
    PROCESSED_DATA_DIR,
    evaluation_dir,
    model_dir,
)

DATA_DIR = PROCESSED_DATA_DIR
OUTPUT_DIR = evaluation_dir("catboost")
MODEL_PATH = model_dir("catboost") / "catboost_tuned_yield.cbm"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET = "kg_per_Acre"

FEATURES = [
    "Year", "Month_Number", "Week_Number",
    "Temperature", "Rainfall_mm", "Humidity",
    "Wind_Speed", "Solar_Radiation",
    "Location", "Grown_Type",
]

CAT_FEATURES = ["Location", "Grown_Type"]

test_df = pd.read_csv(DATA_DIR / "test.csv")

missing = set(FEATURES + [TARGET]) - set(test_df.columns)
if missing:
    raise ValueError(f"test.csv missing columns: {sorted(missing)}")

X_test = test_df[FEATURES].copy()
y_test = test_df[TARGET].astype(float).to_numpy()

for col in CAT_FEATURES:
    X_test[col] = X_test[col].astype(str)

model = CatBoostRegressor()
model.load_model(str(MODEL_PATH))

predictions = model.predict(X_test)

mae = mean_absolute_error(y_test, predictions)
rmse = np.sqrt(mean_squared_error(y_test, predictions))
r2 = r2_score(y_test, predictions)
mape = np.mean(np.abs((y_test - predictions) / y_test)) * 100

metrics = {
    "model": "Tuned CatBoost",
    "test_year": 2025,
    "test_rows": len(test_df),
    "MAE": float(mae),
    "RMSE": float(rmse),
    "R2": float(r2),
    "MAPE_percent": float(mape),
    "parameters": model.get_params(),
}

with open(OUTPUT_DIR / "tuned_test_metrics_2025.json", "w") as f:
    json.dump(metrics, f, indent=4, default=str)

predictions_df = test_df[
    ["Year", "Month_Number", "Week_Number", "Location", TARGET]
].copy()

predictions_df["Predicted_kg_per_Acre"] = predictions
predictions_df["Absolute_Error"] = np.abs(y_test - predictions)

predictions_df.to_csv(
    OUTPUT_DIR / "tuned_test_predictions_2025.csv",
    index=False,
)

print("=" * 55)
print("TUNED CATBOOST - FINAL TEST EVALUATION")
print("=" * 55)
print(f"Test rows: {len(test_df)}")
print(f"MAE:  {mae:.4f}")
print(f"RMSE: {rmse:.4f}")
print(f"R2:   {r2:.4f}")
print(f"MAPE: {mape:.2f}%")
print("\nSaved:")
print(OUTPUT_DIR / "tuned_test_metrics_2025.json")
print(OUTPUT_DIR / "tuned_test_predictions_2025.csv")
print("\nEvaluation complete. No training or tuning performed.")


