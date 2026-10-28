
import json

import joblib
import numpy as np
import pandas as pd

from catboost import CatBoostRegressor
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)

from ml.utils.component02.expected_yield_prediction.paths import (
    PROCESSED_DATA_DIR,
    evaluation_dir,
    model_dir,
)

DATA_DIR = PROCESSED_DATA_DIR
MODEL_DIR = model_dir("catboost")
OUTPUT_DIR = evaluation_dir("catboost")

MODEL_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET = "kg_per_Acre"

FEATURES = [
    "Year",
    "Month_Number",
    "Week_Number",
    "Temperature",
    "Rainfall_mm",
    "Humidity",
    "Wind_Speed",
    "Solar_Radiation",
    "Location",
    "Grown_Type",
]

CATEGORICAL_FEATURES = ["Location", "Grown_Type"]

# Load training and validation datasets
train_df = pd.read_csv(DATA_DIR / "train.csv")
val_df = pd.read_csv(DATA_DIR / "validation.csv")

for name, df in [("train", train_df), ("validation", val_df)]:
    missing = set(FEATURES + [TARGET]) - set(df.columns)
    if missing:
        raise ValueError(
            f"{name}.csv missing columns: {sorted(missing)}"
        )

X_train = train_df[FEATURES].copy()
y_train = train_df[TARGET]

X_val = val_df[FEATURES].copy()
y_val = val_df[TARGET]

# CatBoost handles categorical features directly.
# Convert categorical values to strings.
for col in CATEGORICAL_FEATURES:
    X_train[col] = X_train[col].fillna("Unknown").astype(str)
    X_val[col] = X_val[col].fillna("Unknown").astype(str)

# Train model
model = CatBoostRegressor(
    iterations=500,
    depth=6,
    learning_rate=0.05,
    loss_function="RMSE",
    random_seed=42,
    verbose=100,
    allow_writing_files=False,
)

print("Training CatBoost...")
print(f"Training rows: {len(train_df)}")
print(f"Validation rows: {len(val_df)}")

model.fit(
    X_train,
    y_train,
    cat_features=CATEGORICAL_FEATURES,
    eval_set=(X_val, y_val),
    early_stopping_rounds=50,
    verbose=100,
)

# Validation predictions
predictions = model.predict(X_val)

mae = mean_absolute_error(y_val, predictions)
rmse = np.sqrt(mean_squared_error(y_val, predictions))
r2 = r2_score(y_val, predictions)

actual = y_val.to_numpy()
nonzero = actual != 0

mape = (
    np.mean(
        np.abs(
            (actual[nonzero] - predictions[nonzero])
            / actual[nonzero]
        )
    ) * 100
    if nonzero.any()
    else float("nan")
)

metrics = {
    "model": "CatBoost",
    "target": TARGET,
    "train_years": "2016-2023",
    "validation_year": 2024,
    "train_rows": int(len(train_df)),
    "validation_rows": int(len(val_df)),
    "best_iteration": int(model.get_best_iteration()),
    "MAE": float(mae),
    "RMSE": float(rmse),
    "R2": float(r2),
    "MAPE_percent": float(mape),
}

# Save model
model_path = MODEL_DIR / "catboost_yield.cbm"
model.save_model(str(model_path))

# Save validation metrics
with open(OUTPUT_DIR / "validation_metrics.json", "w") as file:
    json.dump(metrics, file, indent=4)

# Save validation predictions
prediction_df = val_df[
    ["Year", "Month_Number", "Week_Number", "Location", TARGET]
].copy()

prediction_df["Predicted_kg_per_Acre"] = predictions

prediction_df.to_csv(
    OUTPUT_DIR / "validation_predictions.csv",
    index=False,
)

print("\n=== CATBOOST VALIDATION RESULTS ===")
print(f"MAE:  {mae:.4f}")
print(f"RMSE: {rmse:.4f}")
print(f"R2:   {r2:.4f}")
print(f"MAPE: {mape:.2f}%")

print("\nModel saved:", model_path)
print("Metrics saved:", OUTPUT_DIR / "validation_metrics.json")
print("Predictions saved:", OUTPUT_DIR / "validation_predictions.csv")
print("\nCatBoost training complete.")
print("The 2025 test dataset has not been used.")
