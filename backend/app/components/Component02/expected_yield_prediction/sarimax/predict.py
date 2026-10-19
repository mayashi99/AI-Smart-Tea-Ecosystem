"""Forecast from each saved location model's training endpoint (48 periods/year)."""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
TRAIN_PATH = BASE_DIR.parent / "data" / "splits" / "train.csv"
TIME_COLUMNS = ["Year", "Month_Number", "Week_Number"]


def time_index(frame):
    """Use the same four-records-per-month calendar as train.py."""
    missing = set(TIME_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing time columns: {sorted(missing)}")
    values = frame[TIME_COLUMNS].apply(pd.to_numeric, errors="raise")
    if not np.isfinite(values.to_numpy()).all() or (values % 1 != 0).any().any():
        raise ValueError("Year, Month_Number and Week_Number must be finite integers.")
    if not values.Month_Number.between(1, 12).all() or not values.Week_Number.between(1, 4).all():
        raise ValueError("Month_Number must be 1–12 and Week_Number must be 1–4.")
    return (values.Year * 48 + (values.Month_Number - 1) * 4 + values.Week_Number - 1).astype(int)


def load_model(location):
    # The original artifact has no dates, so recover and verify them from train.csv.
    training = pd.read_csv(TRAIN_PATH)
    if not isinstance(location, str) or location not in training["Location"].unique():
        raise ValueError(f"Unknown training location: {location!r}")
    history = training.loc[training.Location == location].copy()
    history["time_index"] = time_index(history)
    history = history.sort_values("time_index")
    if not (np.diff(history.time_index.to_numpy()) == 1).all():
        raise ValueError(f"Training periods for {location} must be unique and consecutive.")
    safe_name = location.lower().replace(" ", "_").replace("/", "_")
    path = BASE_DIR / "models" / f"sarimax_{safe_name}.joblib"
    if not path.is_file():
        raise FileNotFoundError(f"Saved model not found: {path}. Run train.py first.")
    model = joblib.load(path)
    actual = history["kg_per_Acre"].to_numpy(dtype=float)
    saved = np.asarray(model.model.endog, dtype=float).reshape(-1)
    if saved.shape != actual.shape or not np.allclose(saved, actual, equal_nan=False):
        raise ValueError("train.csv does not match the saved model's training history.")
    return model, int(history.time_index.iloc[-1])


def predict_rows(frame):
    """Forecast requested periods without updating the model with observed targets."""
    if "Location" not in frame or frame.empty or frame.Location.isna().any():
        raise ValueError("Provide non-empty input rows with a Location for every row.")
    frame = frame.reset_index(drop=True).copy()
    frame["time_index"] = time_index(frame)
    predictions = np.empty(len(frame), dtype=float)
    for location, rows in frame.groupby("Location", sort=False):
        model, endpoint = load_model(location)
        offsets = rows.time_index.to_numpy() - endpoint
        if (offsets <= 0).any():
            raise ValueError("Prediction periods must be after the model's training endpoint.")
        forecast = np.asarray(model.forecast(steps=int(offsets.max())), dtype=float).reshape(-1)
        predictions[rows.index] = forecast[offsets - 1]
    if not np.isfinite(predictions).all():
        raise ValueError("Model returned non-finite predictions.")
    return predictions


def predict_yield(input_data: dict) -> float:
    """Predict kg/acre using location and time; this model has no weather inputs."""
    if not isinstance(input_data, dict):
        raise ValueError("input_data must be a dictionary containing one input row.")
    return round(float(predict_rows(pd.DataFrame([input_data]))[0]), 2)


if __name__ == "__main__":
    sample_input = {
        "Year": 2026, "Month_Number": 10, "Week_Number": 2,
        "Location": "Nuwara Eliya",
    }
    print("SARIMAX Expected Yield Prediction")
    print(f"Location: {sample_input['Location']}")
    print(f"Predicted yield: {predict_yield(sample_input):.2f} kg/acre")
