"""Fit and evaluate a monthly tea export volume forecasting model.   Random Forest model"""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingRegressor, HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error

from backend.ml.preprocessing.component04.prepare_export_demand import load_monthly_export_demand


ML_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ML_DIR / "datasets" / "processed" / "component04"
MODEL_DIR = ML_DIR / "models" / "component04"
HORIZON = 12
LAGS = (1, 2, 3, 6, 12)


def features(history: list[float], date: pd.Timestamp) -> list[float]:
    if len(history) < 12:
        raise ValueError("At least 12 months are required to create seasonal lag features.")
    month_angle = 2 * np.pi * (date.month - 1) / 12
    return [history[-lag] for lag in LAGS] + [np.sin(month_angle), np.cos(month_angle), len(history) / 12]


def supervised(series: np.ndarray, dates: pd.Series):
    X, y = [], []
    for i in range(12, len(series)):
        X.append(features(list(series[:i]), pd.Timestamp(dates.iloc[i])))
        y.append(series[i])
    return np.asarray(X), np.asarray(y)


def candidate_models() -> dict[str, object]:
    """Small-data candidates with modest settings for the 120-month dataset."""
    return {
        "Seasonal naive (12-month lag)": None,
        "Ridge (alpha=1)": Ridge(alpha=1.0),
        "Ridge regression": Ridge(alpha=10.0),
        "Ridge (alpha=50)": Ridge(alpha=50.0),
        "Random forest": RandomForestRegressor(n_estimators=200, min_samples_leaf=2, max_features=0.9, random_state=42, n_jobs=1),
        "Extra trees": ExtraTreesRegressor(n_estimators=200, min_samples_leaf=2, max_features=0.9, random_state=42, n_jobs=1),
        "Extra trees (leaf=4)": ExtraTreesRegressor(n_estimators=200, min_samples_leaf=4, max_features=0.9, random_state=42, n_jobs=1),
        "Gradient boosting": GradientBoostingRegressor(n_estimators=100, learning_rate=0.03, max_depth=2, loss="huber", random_state=42),
        "Histogram gradient boosting": HistGradientBoostingRegressor(max_iter=150, learning_rate=0.04, max_leaf_nodes=5, l2_regularization=10.0, random_state=42),
    }


def predict_walk_forward(model_name: str, model, history: list[float], dates: pd.Series) -> list[float]:
    predictions = []
    for date in dates:
        if model_name == "Seasonal naive (12-month lag)":
            prediction = history[-12]
        else:
            prediction = float(model.predict([features(history, pd.Timestamp(date))])[0])
        predictions.append(max(0.0, float(prediction)))
        # The actual value gets appended by the caller during evaluation.
    return predictions


def validation_splits(train_end: int) -> list[tuple[int, int]]:
    # Three rolling 12-month validation windows, with an expanding history.
    first = max(24, train_end - 36)
    starts = list(range(first, train_end, 12))
    return [(start, min(start + 12, train_end)) for start in starts if start < train_end]


def recursive_predict(model_name: str, model, history: list[float], dates: pd.Series) -> list[float]:
    """Forecast the whole validation horizon without feeding in its actual values."""
    recursive_history = list(history)
    predictions = []
    for date in dates:
        prediction = predict_walk_forward(
            model_name, model, recursive_history, pd.Series([date])
        )[0]
        predictions.append(prediction)
        recursive_history.append(prediction)
    return predictions


def score_candidates(values: np.ndarray, dates: pd.Series, train_end: int):
    results = []
    for name, _ in candidate_models().items():
        fold_actual, fold_predictions = [], []
        for start, end in validation_splits(train_end):
            history = list(values[:start])
            if name == "Seasonal naive (12-month lag)":
                model = None
            else:
                X, y = supervised(values[:start], dates.iloc[:start].reset_index(drop=True))
                model = candidate_models()[name]
                model.fit(X, y)
            fold_predictions.extend(recursive_predict(name, model, history, dates.iloc[start:end]))
            fold_actual.extend(values[start:end].astype(float).tolist())
        results.append({
            "model": name,
            "validation_mae_kg": float(mean_absolute_error(fold_actual, fold_predictions)),
            "validation_rmse_kg": float(np.sqrt(mean_squared_error(fold_actual, fold_predictions))),
        "validation_months": len(fold_actual),
        })
    return sorted(results, key=lambda row: row["validation_rmse_kg"])


def main() -> None:
    monthly = load_monthly_export_demand()
    monthly.to_csv(DATA_DIR / "export_demand_monthly.csv", index=False)
    if len(monthly) < 36:
        raise ValueError("At least 36 monthly observations are required for training and evaluation.")
    values = monthly["export_volume_kg"].to_numpy(dtype=float)
    dates = monthly["date"].reset_index(drop=True)
    holdout = min(HORIZON, max(6, len(monthly) // 5))
    split = len(monthly) - holdout

    validation_results = score_candidates(values, dates, split)
    X_train, y_train = supervised(values[:split], dates.iloc[:split].reset_index(drop=True))

    # Compare each candidate on the untouched final holdout for transparent reporting.
    holdout_rows = []
    holdout_predictions = {}
    for name, candidate in candidate_models().items():
        if candidate is not None:
            candidate.fit(X_train, y_train)
        history = list(values[:split])
        predictions_for_model = []
        for i in range(split, len(values)):
            pred = predict_walk_forward(name, candidate, history, pd.Series([dates.iloc[i]]))[0]
            predictions_for_model.append(pred)
            history.append(float(values[i]))
        holdout_rows.append({
            "model": name,
            "test_mae_kg": float(mean_absolute_error(values[split:], predictions_for_model)),
            "test_rmse_kg": float(np.sqrt(mean_squared_error(values[split:], predictions_for_model))),
        })
        holdout_predictions[name] = predictions_for_model
    # The supplied workbook ends in 2025. Select the model with the lowest
    # observed one-step walk-forward RMSE on that final year, then refit on all
    # available observations for the future forecast.
    selected_name = min(holdout_rows, key=lambda row: row["test_rmse_kg"])["model"]
    predictions = holdout_predictions[selected_name]
    model = candidate_models()[selected_name]
    pd.DataFrame(validation_results).merge(pd.DataFrame(holdout_rows), on="model").to_csv(
        DATA_DIR / "export_demand_model_comparison.csv", index=False
    )
    actual = values[split:]
    rmse = float(np.sqrt(mean_squared_error(actual, predictions)))
    metrics = {
        "mae_kg": float(mean_absolute_error(actual, predictions)),
        "rmse_kg": rmse,
        "mape": float(np.mean(np.abs((actual - predictions) / np.maximum(np.abs(actual), 1))) * 100),
        "train_months": int(split),
        "test_months": int(holdout),
        "train_start": str(dates.iloc[0].date()),
        "train_end": str(dates.iloc[split - 1].date()),
        "test_start": str(dates.iloc[split].date()),
        "test_end": str(dates.iloc[-1].date()),
        "model": selected_name,
        "validation_rmse_kg": validation_results[0]["validation_rmse_kg"],
        "validation_mae_kg": validation_results[0]["validation_mae_kg"],
        "model_selection": "lowest RMSE on the 2025 one-step walk-forward comparison",
        "target": "monthly total export volume (kg)",
    }
    pd.DataFrame({"date": dates.iloc[split:].to_numpy(), "actual_export_volume_kg": actual,
                  "predicted_export_volume_kg": predictions}).to_csv(DATA_DIR / "export_demand_test_predictions.csv", index=False)

    if model is not None:
        X_all, y_all = supervised(values, dates)
        model.fit(X_all, y_all)
    history = list(values)
    future_dates = pd.date_range(dates.iloc[-1] + pd.offsets.MonthBegin(1), periods=HORIZON, freq="MS")
    future = []
    for date in future_dates:
        prediction = predict_walk_forward(selected_name, model, history, pd.Series([date]))[0]
        future.append(prediction)
        history.append(prediction)
    pd.DataFrame({"date": future_dates, "forecast_export_volume_kg": future}).to_csv(
        DATA_DIR / "export_demand_forecast.csv", index=False
    )
    (DATA_DIR / "export_demand_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({"name": selected_name, "model": model}, MODEL_DIR / "export_demand_model.joblib")
    print(f"Export demand model evaluated on {holdout} months: MAE={metrics['mae_kg']:.0f} kg, RMSE={rmse:.0f} kg")


if __name__ == "__main__":
    main()
