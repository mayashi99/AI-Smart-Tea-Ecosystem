"""Predict yield in kg/acre with the saved Random Forest preprocessing pipeline."""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "models" / "random_forest_yield.joblib"
FEATURES = [
    "Year", "Month_Number", "Week_Number", "Temperature", "Rainfall_mm",
    "Humidity", "Wind_Speed", "Solar_Radiation", "Location", "Grown_Type",
]
NUMERIC_FEATURES = FEATURES[:8]
CATEGORICAL_FEATURES = ["Location", "Grown_Type"]


def load_model():
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(
            f"Model file not found: {MODEL_PATH}. Run train.py first."
        )
    return joblib.load(MODEL_PATH)


def predict_yield(input_data: dict) -> float:
    """Return one prediction using the preprocessing fitted during training."""
    if not isinstance(input_data, dict):
        raise ValueError("input_data must be a dictionary containing one input row.")
    missing = set(FEATURES) - set(input_data)
    if missing:
        raise ValueError(f"Missing required features: {sorted(missing)}")

    input_df = pd.DataFrame([{feature: input_data[feature] for feature in FEATURES}])
    for feature in NUMERIC_FEATURES:
        try:
            value = float(input_data[feature])
        except (TypeError, ValueError):
            raise ValueError(f"{feature} must be a finite number.") from None
        if not np.isfinite(value):
            raise ValueError(f"{feature} must be a finite number.")
        input_df[feature] = value
    for feature in CATEGORICAL_FEATURES:
        value = input_data[feature]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{feature} must be a non-empty string.")

    prediction = float(load_model().predict(input_df)[0])
    if not np.isfinite(prediction):
        raise ValueError("Model returned a non-finite prediction.")
    return round(prediction, 2)


if __name__ == "__main__":
    sample_input = {
        "Year": 2026,
        "Month_Number": 10,
        "Week_Number": 2,
        "Temperature": 23.0,
        "Rainfall_mm": 50.0,
        "Humidity": 84.0,
        "Wind_Speed": 3.0,
        "Solar_Radiation": 215.0,
        "Location": "Nuwara Eliya",
        "Grown_Type": "HIGH grown",
    }
    result = predict_yield(sample_input)
    print("Random Forest Expected Yield Prediction")
    print(f"Location: {sample_input['Location']}")
    print(f"Predicted yield: {result:.2f} kg/acre")
