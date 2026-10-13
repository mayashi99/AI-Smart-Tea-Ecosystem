
from pathlib import Path
import json

import joblib
import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from lightgbm import LGBMRegressor

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
DATA_DIR = PROJECT_DIR / "data" / "splits"
MODEL_DIR = BASE_DIR / "models"
OUTPUT_DIR = BASE_DIR / "outputs"

MODEL_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET = "kg_per_Acre"

train_df = pd.read_csv(DATA_DIR / "train.csv")
val_df = pd.read_csv(DATA_DIR / "validation.csv")

FEATURES = [
    "Year", "Month_Number", "Week_Number",
    "Temperature", "Rainfall_mm", "Humidity",
    "Wind_Speed", "Solar_Radiation",
    "Location", "Grown_Type",
]

NUMERIC_FEATURES = [
    "Year", "Month_Number", "Week_Number",
    "Temperature", "Rainfall_mm", "Humidity",
    "Wind_Speed", "Solar_Radiation",
]
CATEGORICAL_FEATURES = ["Location", "Grown_Type"]

for name, df in [("train", train_df), ("validation", val_df)]:
    missing = set(FEATURES + [TARGET]) - set(df.columns)
    if missing:
        raise ValueError(f"{name}.csv missing columns: {sorted(missing)}")

X_train, y_train = train_df[FEATURES], train_df[TARGET]
X_val, y_val = val_df[FEATURES], val_df[TARGET]

preprocessor = ColumnTransformer([
    ("numeric", SimpleImputer(strategy="median"), NUMERIC_FEATURES),
    ("categorical", Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ]), CATEGORICAL_FEATURES),
])

model = Pipeline([
    ("preprocessor", preprocessor),
    ("model", LGBMRegressor(
        n_estimators=300,
        learning_rate=0.05,
        num_leaves=31,
        random_state=42,
        verbosity=-1,
        n_jobs=4,
    )),
])

print("Training LightGBM...")
print(f"Training rows: {len(train_df)}")
print(f"Validation rows: {len(val_df)}")

model.fit(X_train, y_train)
predictions = model.predict(X_val)

mae = mean_absolute_error(y_val, predictions)
rmse = np.sqrt(mean_squared_error(y_val, predictions))
r2 = r2_score(y_val, predictions)

actual = y_val.to_numpy()
nonzero = actual != 0
mape = (
    np.mean(np.abs((actual[nonzero] - predictions[nonzero]) / actual[nonzero])) * 100
    if nonzero.any()
    else float("nan")
)

metrics = {
    "model": "LightGBM",
    "target": TARGET,
    "train_years": "2016-2023",
    "validation_year": 2024,
    "train_rows": len(train_df),
    "validation_rows": len(val_df),
    "MAE": float(mae),
    "RMSE": float(rmse),
    "R2": float(r2),
    "MAPE_percent": float(mape),
}

joblib.dump(model, MODEL_DIR / "lightgbm_yield.joblib")

with open(OUTPUT_DIR / "validation_metrics.json", "w") as f:
    json.dump(metrics, f, indent=4)

prediction_df = val_df[
    ["Year", "Month_Number", "Week_Number", "Location", TARGET]
].copy()
prediction_df["Predicted_kg_per_Acre"] = predictions
prediction_df.to_csv(OUTPUT_DIR / "validation_predictions.csv", index=False)

print("\n=== LIGHTGBM VALIDATION RESULTS ===")
print(f"MAE:  {mae:.4f}")
print(f"RMSE: {rmse:.4f}")
print(f"R2:   {r2:.4f}")
print(f"MAPE: {mape:.2f}%")

print("\nModel saved:", MODEL_DIR / "lightgbm_yield.joblib")
print("Metrics saved:", OUTPUT_DIR / "validation_metrics.json")
print("Predictions saved:", OUTPUT_DIR / "validation_predictions.csv")
print("\nLightGBM training complete.")
print("The 2025 test dataset has not been used.")
