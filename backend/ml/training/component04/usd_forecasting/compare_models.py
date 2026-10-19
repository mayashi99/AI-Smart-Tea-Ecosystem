"""Compare USD/LKR daily forecasters and write 30-business-day projections."""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

from backend.ml.training.component04.usd_forecasting.models.extra_trees.model import (
    create_model as create_extra_trees,
)
from backend.ml.training.component04.usd_forecasting.models.ridge.model import (
    create_model as create_ridge,
)


ML_DIR = Path(__file__).resolve().parents[3]
RAW_FILE = ML_DIR / "datasets" / "raw" / "component04" / "US_Doller_Data.csv"
OUTPUT_DIR = ML_DIR / "datasets" / "processed" / "component04" / "usd_forecasting"
MODEL_DIR = ML_DIR / "models" / "component04" / "usd_forecasting"
LOOKBACK = 60
HORIZON_BUSINESS_DAYS = 30
TEST_FRACTION = 0.2

MODEL_FACTORIES = {
    "ridge": create_ridge,
    "extra_trees": create_extra_trees,
}


def load_history(path: Path) -> pd.DataFrame:
    required = {"Currency", "Date", "Exchange Rate"}
    history = pd.read_csv(path)
    missing_columns = required.difference(history.columns)
    if missing_columns:
        raise ValueError(f"USD exchange-rate CSV is missing columns: {sorted(missing_columns)}")

    history = history.loc[
        history["Currency"].astype(str).str.upper().eq("USD"),
        ["Date", "Exchange Rate"],
    ].copy()
    history["Date"] = pd.to_datetime(history["Date"], errors="coerce")
    history["Exchange Rate"] = pd.to_numeric(history["Exchange Rate"], errors="coerce")
    invalid_rows = int(history[["Date", "Exchange Rate"]].isna().any(axis=1).sum())
    if invalid_rows:
        print(f"Dropping {invalid_rows} USD row(s) with invalid dates or exchange rates.")
    history = history.dropna(subset=["Date", "Exchange Rate"])
    history = history.sort_values("Date").reset_index(drop=True)

    if history["Date"].duplicated().any():
        duplicates = history.loc[history["Date"].duplicated(), "Date"].dt.strftime("%Y-%m-%d").tolist()
        raise ValueError(f"USD exchange-rate history contains duplicate dates: {duplicates[:5]}")
    if len(history) <= LOOKBACK + 1:
        raise ValueError(f"At least {LOOKBACK + 2} valid USD observations are required.")
    if (history["Exchange Rate"] <= 0).any():
        raise ValueError("USD exchange rates must be positive.")
    return history


def make_features(values: np.ndarray, index: int, date: pd.Timestamp) -> list[float]:
    if index < LOOKBACK or index > len(values):
        raise ValueError(f"Feature index must be between {LOOKBACK} and {len(values)}.")
    prior = values[:index]
    windows = (5, 20, LOOKBACK)
    angle = 2 * np.pi * (date.dayofyear - 1) / 365.25
    weekday_angle = 2 * np.pi * date.weekday() / 5
    return (
        [float(prior[-lag]) for lag in (1, 2, 5, 10, 20, 40, LOOKBACK)]
        + [float(np.mean(prior[-window:])) for window in windows]
        + [float(np.std(prior[-window:])) for window in windows]
        + [float(prior[-1] - prior[-lag]) for lag in (2, 5, 20, LOOKBACK)]
        + [float(index), float(np.sin(angle)), float(np.cos(angle)),
           float(np.sin(weekday_angle)), float(np.cos(weekday_angle))]
    )


def build_training_data(values: np.ndarray, dates: pd.Series, end: int):
    features = [
        make_features(values, i, pd.Timestamp(dates.iloc[i]))
        for i in range(LOOKBACK, end)
    ]
    targets = values[LOOKBACK:end]
    return np.asarray(features, dtype=float), np.asarray(targets, dtype=float)


def score_predictions(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    return {
        "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(np.sqrt(mean_squared_error(actual, predicted))),
        "mape": float(np.mean(np.abs((actual - predicted) / actual)) * 100),
    }


def forecast_future(model, values: np.ndarray, last_date: pd.Timestamp, horizon: int):
    forecast_dates = pd.bdate_range(
        start=last_date + pd.offsets.BDay(1),
        periods=horizon,
    )
    history = list(map(float, values))
    predictions = []
    for step, date in enumerate(forecast_dates):
        features = make_features(np.asarray(history), len(history), pd.Timestamp(date))
        prediction = float(model.predict(np.asarray(features).reshape(1, -1))[0])
        predictions.append(prediction)
        history.append(prediction)
    return forecast_dates, np.asarray(predictions, dtype=float)


def compare_models(
    raw_file: Path = RAW_FILE,
    output_dir: Path = OUTPUT_DIR,
    model_dir: Path = MODEL_DIR,
    horizon: int = HORIZON_BUSINESS_DAYS,
) -> pd.DataFrame:
    history = load_history(raw_file)
    values = history["Exchange Rate"].to_numpy(dtype=float)
    dates = history["Date"].reset_index(drop=True)
    train_end = max(LOOKBACK + 1, int(len(history) * 0.7))
    validation_end = max(train_end + 1, int(len(history) * (1 - TEST_FRACTION)))
    if validation_end >= len(history):
        raise ValueError("Not enough observations remain for validation and test sets.")

    x_train, y_train = build_training_data(values, dates, train_end)
    validation_features = np.asarray([
        make_features(values, i, pd.Timestamp(dates.iloc[i]))
        for i in range(train_end, validation_end)
    ])
    validation_actual = values[train_end:validation_end]
    x_development, y_development = build_training_data(values, dates, validation_end)
    test_features = np.asarray([
        make_features(values, i, pd.Timestamp(dates.iloc[i]))
        for i in range(validation_end, len(values))
    ])
    test_actual = values[validation_end:]
    rows = []
    output_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)

    for model_name, factory in MODEL_FACTORIES.items():
        validation_model = factory()
        validation_model.fit(x_train, y_train)
        validation_predictions = np.asarray(
            validation_model.predict(validation_features), dtype=float
        )
        validation_metrics = score_predictions(
            validation_actual, validation_predictions
        )
        test_model = factory()
        test_model.fit(x_development, y_development)
        test_predictions = np.asarray(test_model.predict(test_features), dtype=float)
        test_metrics = score_predictions(test_actual, test_predictions)
        rows.append({
            "model": model_name,
            "validation_start": str(dates.iloc[train_end].date()),
            "validation_end": str(dates.iloc[validation_end - 1].date()),
            "validation_observations": len(validation_actual),
            "validation_mae_lkr_per_usd": validation_metrics["mae"],
            "validation_rmse_lkr_per_usd": validation_metrics["rmse"],
            "validation_mape_percent": validation_metrics["mape"],
            "test_start": str(dates.iloc[validation_end].date()),
            "test_end": str(dates.iloc[-1].date()),
            "test_observations": len(test_actual),
            "test_mae_lkr_per_usd": test_metrics["mae"],
            "test_rmse_lkr_per_usd": test_metrics["rmse"],
            "test_mape_percent": test_metrics["mape"],
        })

        per_model_output = output_dir / model_name
        per_model_output.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({
            "date": dates.iloc[train_end:validation_end].dt.strftime("%Y-%m-%d"),
            "actual_lkr_per_usd": validation_actual,
            "predicted_lkr_per_usd": validation_predictions,
        }).to_csv(per_model_output / "validation_predictions.csv", index=False)
        pd.DataFrame({
            "date": dates.iloc[validation_end:].dt.strftime("%Y-%m-%d"),
            "actual_lkr_per_usd": test_actual,
            "predicted_lkr_per_usd": test_predictions,
        }).to_csv(per_model_output / "test_predictions.csv", index=False)

    comparison = pd.DataFrame(rows).sort_values(
        ["validation_mae_lkr_per_usd", "validation_rmse_lkr_per_usd"]
    ).reset_index(drop=True)
    comparison.insert(0, "rank", np.arange(1, len(comparison) + 1))
    comparison.to_csv(output_dir / "model_comparison.csv", index=False)

    forecasts = {}
    for row in comparison.itertuples(index=False):
        model_name = row.model
        model = MODEL_FACTORIES[model_name]()
        x_all, y_all = build_training_data(values, dates, len(values))
        model.fit(x_all, y_all)
        forecast_dates, predictions = forecast_future(
            model, values, pd.Timestamp(dates.iloc[-1]), horizon
        )
        model_forecast = pd.DataFrame({
            "date": forecast_dates.strftime("%Y-%m-%d"),
            "forecast_lkr_per_usd": predictions,
        })
        model_output = output_dir / model_name
        model_forecast.to_csv(model_output / "forecast.csv", index=False)
        model_artifact_dir = model_dir / model_name
        model_artifact_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, model_artifact_dir / "model.joblib")
        forecasts[model_name] = predictions
        model_forecast.to_csv(model_artifact_dir / "forecast.csv", index=False)

    comparison_dates = pd.bdate_range(
        start=pd.Timestamp(dates.iloc[-1]) + pd.offsets.BDay(1),
        periods=horizon,
    )
    pd.DataFrame({
        "date": comparison_dates.strftime("%Y-%m-%d"),
        **{f"{name}_forecast_lkr_per_usd": values for name, values in forecasts.items()},
    }).to_csv(output_dir / "forecast_comparison.csv", index=False)

    metadata = {
        "target": "USD/LKR exchange rate (LKR per USD)",
        "frequency": "daily trading observations; forecast dates use weekdays",
        "forecast_horizon_business_days": horizon,
        "selection": "ranked by chronological validation MAE, then RMSE",
        "training_observations": len(values),
        "training_start": str(dates.iloc[0].date()),
        "training_end": str(dates.iloc[-1].date()),
        "validation_start": str(dates.iloc[train_end].date()),
        "validation_end": str(dates.iloc[validation_end - 1].date()),
        "test_start": str(dates.iloc[validation_end].date()),
        "test_end": str(dates.iloc[-1].date()),
        "best_model": str(comparison.iloc[0]["model"]),
    }
    (output_dir / "forecast_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    print(
        "Model comparison (ranked by validation; lower MAE is better):\n"
        + comparison[["rank", "model", "validation_mae_lkr_per_usd",
                      "test_mae_lkr_per_usd", "test_rmse_lkr_per_usd"]].to_string(index=False)
    )
    return comparison


if __name__ == "__main__":
    compare_models()
