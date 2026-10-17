
from pathlib import Path
import json

import joblib
import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)

from ngboost import NGBRegressor
from ngboost.distns import Normal
from ngboost.scores import MLE


# --------------------------------------------------
# 1. Paths
# --------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent

DATA_DIR = PROJECT_DIR / "data" / "splits"
MODEL_DIR = BASE_DIR / "models"
OUTPUT_DIR = BASE_DIR / "outputs"

MODEL_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET = "kg_per_Acre"


# --------------------------------------------------
# 2. Load datasets
# --------------------------------------------------
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

NUMERIC_FEATURES = [
    "Year",
    "Month_Number",
    "Week_Number",
    "Temperature",
    "Rainfall_mm",
    "Humidity",
    "Wind_Speed",
    "Solar_Radiation",
]

CATEGORICAL_FEATURES = [
    "Location",
    "Grown_Type",
]


# --------------------------------------------------
# 3. Validate required columns
# --------------------------------------------------
for name, df in [
    ("train", train_df),
    ("validation", val_df),
]:
    missing = set(FEATURES + [TARGET]) - set(df.columns)

    if missing:
        raise ValueError(
            f"{name}.csv missing columns: {sorted(missing)}"
        )

X_train = train_df[FEATURES]
y_train = train_df[TARGET]

X_val = val_df[FEATURES]
y_val = val_df[TARGET]


# --------------------------------------------------
# 4. Preprocessing
# Fit preprocessing ONLY on training data
# --------------------------------------------------
preprocessor = ColumnTransformer([
    (
        "numeric",
        SimpleImputer(strategy="median"),
        NUMERIC_FEATURES,
    ),
    (
        "categorical",
        Pipeline([
            (
                "imputer",
                SimpleImputer(strategy="most_frequent"),
            ),
            (
                "onehot",
                OneHotEncoder(handle_unknown="ignore"),
            ),
        ]),
        CATEGORICAL_FEATURES,
    ),
])

print("=" * 55)
print("NGBOOST YIELD MODEL TRAINING")
print("=" * 55)

print(f"Training rows: {len(train_df)}")
print(f"Validation rows: {len(val_df)}")

print("\nFitting preprocessor...")

X_train_transformed = preprocessor.fit_transform(X_train)
X_val_transformed = preprocessor.transform(X_val)


# --------------------------------------------------
# 5. Train NGBoost
# --------------------------------------------------
print("\nTraining NGBoost model...")

ngb_model = NGBRegressor(
    Dist=Normal,
    Score=MLE,
    n_estimators=300,
    learning_rate=0.03,
    random_state=42,
    verbose=False,
)

ngb_model.fit(X_train_transformed, y_train)

print("NGBoost model fitted successfully.")


# --------------------------------------------------
# 6. Validation predictions
# --------------------------------------------------
print("\nGenerating validation predictions...")

predictions = ngb_model.predict(X_val_transformed)


# --------------------------------------------------
# 7. Calculate evaluation metrics
# --------------------------------------------------
mae = mean_absolute_error(y_val, predictions)

rmse = np.sqrt(
    mean_squared_error(y_val, predictions)
)

r2 = r2_score(y_val, predictions)

actual = y_val.to_numpy()
nonzero = actual != 0

if nonzero.any():
    mape = np.mean(
        np.abs(
            (actual[nonzero] - predictions[nonzero])
            / actual[nonzero]
        )
    ) * 100
else:
    mape = float("nan")


metrics = {
    "model": "NGBoost",
    "target": TARGET,
    "train_years": "2016-2023",
    "validation_year": 2024,
    "train_rows": int(len(train_df)),
    "validation_rows": int(len(val_df)),
    "MAE": float(mae),
    "RMSE": float(rmse),
    "R2": float(r2),
    "MAPE_percent": float(mape),
}


# --------------------------------------------------
# 8. Save model and preprocessor
# --------------------------------------------------
model_path = MODEL_DIR / "ngboost_yield.joblib"

joblib.dump(
    {
        "model": ngb_model,
        "preprocessor": preprocessor,
        "feature_columns": FEATURES,
        "target": TARGET,
    },
    model_path,
)


# --------------------------------------------------
# 9. Save metrics
# --------------------------------------------------
metrics_path = OUTPUT_DIR / "validation_metrics.json"

with open(metrics_path, "w") as file:
    json.dump(metrics, file, indent=4)


# --------------------------------------------------
# 10. Save validation predictions
# --------------------------------------------------
prediction_df = val_df[
    [
        "Year",
        "Month_Number",
        "Week_Number",
        "Location",
        TARGET,
    ]
].copy()

prediction_df["Predicted_kg_per_Acre"] = predictions

predictions_path = (
    OUTPUT_DIR / "validation_predictions.csv"
)

prediction_df.to_csv(
    predictions_path,
    index=False,
)


# --------------------------------------------------
# 11. Print results
# --------------------------------------------------
print("\n" + "=" * 55)
print("NGBOOST VALIDATION RESULTS")
print("=" * 55)

print(f"MAE:  {mae:.4f}")
print(f"RMSE: {rmse:.4f}")
print(f"R2:   {r2:.4f}")
print(f"MAPE: {mape:.2f}%")

print("\nSaved model:", model_path)
print("Saved metrics:", metrics_path)
print("Saved predictions:", predictions_path)

print("\nNGBoost training completed successfully.")
print("The 2025 test dataset has not been used.")
