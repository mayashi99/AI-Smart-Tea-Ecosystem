"""LightGBM yield inference using the saved preprocessing/model pipeline."""
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from ml.feature_engineering.component02.expected_yield_prediction.features import (
    CATEGORICAL_FEATURES,
    FEATURES,
    NUMERIC_FEATURES,
)
from ml.utils.component02.expected_yield_prediction.paths import model_dir

BASE_DIR = model_dir("lightgbm")
MODEL_PATH = BASE_DIR / "lightgbm_yield.joblib"


def load_model(model_path=MODEL_PATH):
    """Load the fitted pipeline without retraining its preprocessing steps."""
    path = Path(model_path)
    if not path.is_file():
        raise FileNotFoundError(f"LightGBM model file not found: {path}")
    return joblib.load(path)


def prepare_features(data):
    """Validate complete input rows and retain the training feature order."""
    frame = pd.DataFrame([data]) if isinstance(data, dict) else pd.DataFrame(data).copy()
    missing = set(FEATURES) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing required features: {sorted(missing)}")
    if frame.empty:
        raise ValueError("At least one input row is required.")
    frame = frame[FEATURES].copy()
    for column in NUMERIC_FEATURES:
        if frame[column].map(lambda value: isinstance(value, (bool, np.bool_))).any():
            raise ValueError(f"{column} must contain numeric values, not booleans.")
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if not np.isfinite(frame[column].to_numpy(dtype=float)).all():
            raise ValueError(f"{column} must contain finite numeric values.")
    for column, low, high in [("Year", 2016, 2100), ("Month_Number", 1, 12), ("Week_Number", 1, 4)]:
        if not (frame[column].between(low, high) & (frame[column] % 1 == 0)).all():
            raise ValueError(f"{column} must be an integer between {low} and {high}.")
    if not frame.Humidity.between(0, 100).all():
        raise ValueError("Humidity must be between 0 and 100.")
    for column in ["Rainfall_mm", "Wind_Speed", "Solar_Radiation"]:
        if (frame[column] < 0).any():
            raise ValueError(f"{column} cannot be negative.")
    for column in CATEGORICAL_FEATURES:
        if not frame[column].map(lambda value: isinstance(value, str) and bool(value.strip())).all():
            raise ValueError(f"{column} must contain nonempty strings.")
    if not frame.Grown_Type.isin(["HIGH grown", "MID grown", "LOW grown"]).all():
        raise ValueError("Grown_Type must be HIGH grown, MID grown, or LOW grown.")
    return frame


def predict_yield(input_data, model_path=MODEL_PATH):
    """Return one weekly kg/acre estimate, rounded for display."""
    frame = prepare_features(input_data)
    if len(frame) != 1:
        raise ValueError("predict_yield accepts exactly one input row.")
    prediction = float(load_model(model_path).predict(frame)[0])
    if not np.isfinite(prediction):
        raise ValueError("The model returned a non-finite yield prediction.")
    return round(prediction, 2)


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Predict LightGBM yield from a JSON input file.")
    parser.add_argument("input", type=Path, help="JSON object containing the ten model input fields")
    args = parser.parse_args()
    with args.input.open(encoding="utf-8") as source:
        result = predict_yield(json.load(source))
    print(json.dumps({"model": "LightGBM", "predicted_kg_per_Acre": result, "unit": "kg/acre"}))
