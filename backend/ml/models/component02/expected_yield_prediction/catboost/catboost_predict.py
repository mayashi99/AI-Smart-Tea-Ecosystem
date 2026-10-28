
import pandas as pd
from catboost import CatBoostRegressor

from ml.feature_engineering.component02.expected_yield_prediction.features import (
    CATEGORICAL_FEATURES,
    FEATURES,
)
from ml.utils.component02.expected_yield_prediction.paths import model_dir

MODEL_PATH = model_dir("catboost") / "catboost_yield.cbm"


def load_model():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model file not found: {MODEL_PATH}"
        )

    model = CatBoostRegressor()
    model.load_model(str(MODEL_PATH))
    return model


def predict_yield(input_data: dict) -> float:
    missing = set(FEATURES) - set(input_data.keys())

    if missing:
        raise ValueError(
            f"Missing required features: {sorted(missing)}"
        )

    input_df = pd.DataFrame(
        [{feature: input_data[feature] for feature in FEATURES}]
    )

    for column in CATEGORICAL_FEATURES:
        input_df[column] = input_df[column].astype(str)

    model = load_model()
    prediction = model.predict(input_df)[0]

    return round(float(prediction), 2)


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

    print("Expected Yield Prediction")
    print(f"Location: {sample_input['Location']}")
    print(f"Predicted yield: {result} kg/acre")

