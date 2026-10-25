
from pathlib import Path
import json

import joblib
import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# Paths
BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
DATA_DIR = PROJECT_DIR / "data" / "splits"
MODEL_DIR = BASE_DIR / "models"
OUTPUT_DIR = BASE_DIR / "outputs"

MODEL_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET = "kg_per_Acre"

# Load chronological splits
train_df = pd.read_csv(DATA_DIR / "train.csv")
val_df = pd.read_csv(DATA_DIR / "validation.csv")

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

required = FEATURES + [TARGET]

for name, df in [("train", train_df), ("validation", val_df)]:
    missing = set(required) - set(df.columns)
    if missing:
        raise ValueError(f"{name}.csv missing columns: {sorted(missing)}")

X_train = train_df[FEATURES]
y_train = train_df[TARGET]
X_val = val_df[FEATURES]
y_val = val_df[TARGET]

numeric_features = [
    "Year", "Month_Number", "Week_Number",
    "Temperature", "Rainfall_mm", "Humidity",
    "Wind_Speed", "Solar_Radiation",
]
categorical_features = ["Location", "Grown_Type"]

preprocessor = ColumnTransformer([
    (
        "numeric",
        SimpleImputer(strategy="median"),
        numeric_features,
    ),
    (
        "categorical",
        Pipeline([
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]),
        categorical_features,
    ),
])

model = Pipeline([
    ("preprocessor", preprocessor),
    ("model", RandomForestRegressor(
        n_estimators=300,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1,
    )),
])

print("Training Random Forest...")
print(f"Training rows: {len(train_df)}")
print(f"Validation rows: {len(val_df)}")

model.fit(X_train, y_train)
predictions = model.predict(X_val)

mae = mean_absolute_error(y_val, predictions)
rmse = np.sqrt(mean_squared_error(y_val, predictions))
r2 = r2_score(y_val, predictions)

nonzero = y_val.to_numpy() != 0
mape = (
    np.mean(
        np.abs(
            (y_val.to_numpy()[nonzero] - predictions[nonzero])
            / y_val.to_numpy()[nonzero]
        )
    ) * 100
    if nonzero.any()
    else float("nan")
)

metrics = {
    "model": "Random Forest",
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

# Save trained model
joblib.dump(model, MODEL_DIR / "random_forest_yield.joblib")

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

print("\n=== RANDOM FOREST VALIDATION RESULTS ===")
print(f"MAE:  {mae:.4f}")
print(f"RMSE: {rmse:.4f}")
print(f"R2:   {r2:.4f}")
print(f"MAPE: {mape:.2f}%")

print("\nModel saved:", MODEL_DIR / "random_forest_yield.joblib")
print("Metrics saved:", OUTPUT_DIR / "validation_metrics.json")
print("Predictions saved:", OUTPUT_DIR / "validation_predictions.csv")
print("\nRandom Forest training complete.")
print("The 2025 test dataset has not been used.")
