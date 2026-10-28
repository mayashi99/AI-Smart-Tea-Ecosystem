
import json
import warnings

import joblib
import numpy as np
import pandas as pd

from statsmodels.tsa.statespace.sarimax import SARIMAX
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)

warnings.filterwarnings("ignore")

from ml.utils.component02.expected_yield_prediction.paths import PROCESSED_DATA_DIR, evaluation_dir, model_dir

DATA_DIR = PROCESSED_DATA_DIR
MODEL_DIR = model_dir("sarimax")
OUTPUT_DIR = evaluation_dir("sarimax")

MODEL_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET = "kg_per_Acre"
LOCATION_COL = "Location"

train_df = pd.read_csv(DATA_DIR / "train.csv")
val_df = pd.read_csv(DATA_DIR / "validation.csv")

required = {"Year", "Month_Number", "Week_Number", LOCATION_COL, TARGET}

for name, df in [("train", train_df), ("validation", val_df)]:
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{name}.csv missing columns: {sorted(missing)}")

# Create a chronological week index within each year.
# The source data has four records per month.
def add_time_index(df):
    df = df.copy()
    df["time_index"] = (
        df["Year"] * 48
        + (df["Month_Number"] - 1) * 4
        + (df["Week_Number"] - 1)
    )
    return df

train_df = add_time_index(train_df)
val_df = add_time_index(val_df)

all_locations = sorted(train_df[LOCATION_COL].unique())
results = []
prediction_frames = []
fitted_models = {}

print("Training SARIMAX models by location...")
print(f"Locations: {len(all_locations)}")
print(f"Training rows: {len(train_df)}")
print(f"Validation rows: {len(val_df)}")

for location in all_locations:
    train_loc = train_df[train_df[LOCATION_COL] == location].sort_values("time_index")
    val_loc = val_df[val_df[LOCATION_COL] == location].sort_values("time_index")

    y_train = train_loc[TARGET].astype(float).to_numpy()
    y_val = val_loc[TARGET].astype(float).to_numpy()

    if len(y_train) < 48 or len(y_val) == 0:
        print(f"Skipping {location}: insufficient data")
        continue

    try:
        # Seasonal period 48 = 12 months * 4 weeks per month.
        # A non-seasonal model is used initially for practical runtime.
        model = SARIMAX(
            y_train,
            order=(1, 1, 1),
            seasonal_order=(0, 0, 0, 0),
            enforce_stationarity=False,
            enforce_invertibility=False,
        )

        fitted = model.fit(disp=False, maxiter=100)

        forecast = np.asarray(fitted.forecast(steps=len(y_val)))

        mae = mean_absolute_error(y_val, forecast)
        rmse = np.sqrt(mean_squared_error(y_val, forecast))
        r2 = r2_score(y_val, forecast) if len(y_val) > 1 else float("nan")

        nonzero = y_val != 0
        mape = (
            np.mean(np.abs((y_val[nonzero] - forecast[nonzero]) / y_val[nonzero])) * 100
            if nonzero.any()
            else float("nan")
        )

        results.append({
            "Location": location,
            "Train_Rows": len(train_loc),
            "Validation_Rows": len(val_loc),
            "MAE": float(mae),
            "RMSE": float(rmse),
            "R2": float(r2),
            "MAPE_percent": float(mape),
        })

        pred = val_loc[
            ["Year", "Month_Number", "Week_Number", "Location", TARGET]
        ].copy()
        pred["Predicted_kg_per_Acre"] = forecast
        prediction_frames.append(pred)

        fitted_models[location] = fitted

        print(f"{location}: MAE={mae:.4f}, RMSE={rmse:.4f}, R2={r2:.4f}")

    except Exception as exc:
        print(f"Failed for {location}: {exc}")

if not results:
    raise RuntimeError("No SARIMAX models were trained successfully.")

results_df = pd.DataFrame(results)
predictions_df = pd.concat(prediction_frames, ignore_index=True)

# Overall metrics across all validation predictions
actual = predictions_df[TARGET].to_numpy()
predicted = predictions_df["Predicted_kg_per_Acre"].to_numpy()

overall_mae = mean_absolute_error(actual, predicted)
overall_rmse = np.sqrt(mean_squared_error(actual, predicted))
overall_r2 = r2_score(actual, predicted)

nonzero = actual != 0
overall_mape = (
    np.mean(np.abs((actual[nonzero] - predicted[nonzero]) / actual[nonzero])) * 100
    if nonzero.any()
    else float("nan")
)

metrics = {
    "model": "SARIMAX",
    "target": TARGET,
    "train_years": "2016-2023",
    "validation_year": 2024,
    "locations_trained": len(results),
    "MAE": float(overall_mae),
    "RMSE": float(overall_rmse),
    "R2": float(overall_r2),
    "MAPE_percent": float(overall_mape),
    "note": "Separate univariate SARIMAX model per location; no 2025 test data used.",
}

with open(OUTPUT_DIR / "validation_metrics.json", "w") as f:
    json.dump(metrics, f, indent=4)

results_df.to_csv(OUTPUT_DIR / "location_validation_metrics.csv", index=False)
predictions_df.to_csv(OUTPUT_DIR / "validation_predictions.csv", index=False)

# Save each fitted location model separately
for location, fitted in fitted_models.items():
    safe_name = (
        location.lower()
        .replace(" ", "_")
        .replace("/", "_")
    )
    joblib.dump(fitted, MODEL_DIR / f"sarimax_{safe_name}.joblib")

print("\n=== SARIMAX OVERALL VALIDATION RESULTS ===")
print(f"MAE:  {overall_mae:.4f}")
print(f"RMSE: {overall_rmse:.4f}")
print(f"R2:   {overall_r2:.4f}")
print(f"MAPE: {overall_mape:.2f}%")
print(f"\nLocations trained: {len(results)}")
print("Metrics saved:", OUTPUT_DIR / "validation_metrics.json")
print("Location metrics saved:", OUTPUT_DIR / "location_validation_metrics.csv")
print("Predictions saved:", OUTPUT_DIR / "validation_predictions.csv")
print("\nSARIMAX training complete.")
print("The 2025 test dataset has not been used.")
