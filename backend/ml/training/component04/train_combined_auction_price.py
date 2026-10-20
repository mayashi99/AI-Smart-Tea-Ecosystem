"""Select and train a monthly auction price model from the combined workbook."""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingRegressor, HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error

from backend.ml.preprocessing.component04.prepare_combined_auction_price import load_monthly_data


ML_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ML_DIR / "datasets" / "processed" / "component04"
MODEL_DIR = ML_DIR / "models" / "component04"
HORIZON = 12
LAGS = (1, 2, 3, 6, 12)


def features(history: list[float], date: pd.Timestamp) -> list[float]:
    if len(history) < 12:
        raise ValueError("At least 12 monthly prices are required.")
    angle = 2 * np.pi * (date.month - 1) / 12
    return (
        [history[-lag] for lag in LAGS]
        + [float(np.mean(history[-window:])) for window in (3, 6, 12)]
        + [np.sin(angle), np.cos(angle), len(history) / 12]
    )


def supervised(values: np.ndarray, dates: pd.Series):
    X, y = [], []
    for i in range(12, len(values)):
        X.append(features(list(values[:i]), pd.Timestamp(dates.iloc[i])))
        y.append(values[i])
    return np.asarray(X), np.asarray(y)


def models() -> dict[str, object]:
    return {
        "Last month baseline": None,
        "Seasonal naive (12 months)": "seasonal",
        "Ridge (alpha=1)": Ridge(alpha=1.0),
        "Ridge (alpha=10)": Ridge(alpha=10.0),
        "Random forest": RandomForestRegressor(n_estimators=250, min_samples_leaf=2, max_features=0.9, random_state=42, n_jobs=1),
        "Extra trees": ExtraTreesRegressor(n_estimators=250, min_samples_leaf=2, max_features=0.9, random_state=42, n_jobs=1),
        "Gradient boosting": GradientBoostingRegressor(n_estimators=100, learning_rate=0.03, max_depth=2, loss="huber", random_state=42),
        "Histogram gradient boosting": HistGradientBoostingRegressor(max_iter=150, learning_rate=0.04, max_leaf_nodes=5, l2_regularization=10.0, random_state=42),
    }


def predict_one(name: str, model, history: list[float], date: pd.Timestamp) -> float:
    if name == "Last month baseline":
        return float(history[-1])
    if name == "Seasonal naive (12 months)":
        return float(history[-12])
    prediction = float(model.predict([features(history, date)])[0])
    return max(0.0, prediction)


def rolling_score(values: np.ndarray, dates: pd.Series, model_name: str, factory, end: int):
    # Expanding one-year folds entirely before the 2025 final test year.
    folds = [(start, min(start + 12, end)) for start in range(max(48, end - 36), end, 12)]
    actual, predicted = [], []
    for start, stop in folds:
        model = factory
        history = list(values[:start])
        if model not in (None, "seasonal"):
            X, y = supervised(values[:start], dates.iloc[:start].reset_index(drop=True))
            model.fit(X, y)
        for i in range(start, stop):
            predicted.append(predict_one(model_name, model, history, pd.Timestamp(dates.iloc[i])))
            actual.append(float(values[i]))
            history.append(float(values[i]))
    return float(np.sqrt(mean_squared_error(actual, predicted))), float(mean_absolute_error(actual, predicted)), len(actual)


def main() -> None:
    monthly = load_monthly_data()
    monthly.to_csv(DATA_DIR / "combined_auction_price_monthly.csv", index=False)
    values = monthly["avg_price_lkr"].to_numpy(dtype=float)
    dates = monthly["date"].reset_index(drop=True)
    # Use the complete 2025 calendar year as an untouched chronological test set.
    test_indices = np.flatnonzero(dates.dt.year.eq(2025).to_numpy())
    if len(test_indices) != 12:
        raise ValueError("The workbook must contain all 12 months of 2025 for model evaluation.")
    split = int(test_indices[0])
    if not np.array_equal(test_indices, np.arange(split, split + 12)):
        raise ValueError("2025 rows must be consecutive monthly observations.")

    ranking = []
    for name, factory in models().items():
        cv_rmse, cv_mae, cv_months = rolling_score(values, dates, name, factory, split)
        ranking.append({"model": name, "validation_rmse_lkr": cv_rmse, "validation_mae_lkr": cv_mae, "validation_months": cv_months})
    ranking.sort(key=lambda row: row["validation_rmse_lkr"])
    selected_name = ranking[0]["model"]

    X_train, y_train = supervised(values[:split], dates.iloc[:split].reset_index(drop=True))
    test_results, predictions_by_model = [], {}
    for name, factory in models().items():
        model = factory
        if model not in (None, "seasonal"):
            model.fit(X_train, y_train)
        history, predictions = list(values[:split]), []
        for i in test_indices:
            predictions.append(predict_one(name, model, history, pd.Timestamp(dates.iloc[i])))
            history.append(float(values[i]))
        predictions_by_model[name] = predictions
        test_results.append({
            "model": name,
            "test_mae_lkr": float(mean_absolute_error(values[test_indices], predictions)),
            "test_rmse_lkr": float(np.sqrt(mean_squared_error(values[test_indices], predictions))),
        })
    ranking_df = pd.DataFrame(ranking).merge(pd.DataFrame(test_results), on="model")
    ranking_df.to_csv(DATA_DIR / "combined_auction_price_model_comparison.csv", index=False)
    test_predictions = predictions_by_model[selected_name]
    pd.DataFrame({
        "date": dates.iloc[test_indices],
        "actual_avg_price_lkr": values[test_indices],
        "predicted_avg_price_lkr": test_predictions,
    }).to_csv(DATA_DIR / "combined_auction_price_test_predictions.csv", index=False)

    # Refit the selected model through the latest available month (July 2026).
    X_all, y_all = supervised(values, dates)
    factory = models()[selected_name]
    final_model = factory
    if final_model not in (None, "seasonal"):
        final_model.fit(X_all, y_all)
    history = list(values)
    future_dates = pd.date_range(dates.iloc[-1] + pd.offsets.MonthBegin(1), periods=HORIZON, freq="MS")
    future = []
    for date in future_dates:
        price = predict_one(selected_name, final_model, history, date)
        future.append(price)
        history.append(price)
    pd.DataFrame({"date": future_dates, "forecast_avg_price_lkr": future}).to_csv(
        DATA_DIR / "combined_auction_price_forecast.csv", index=False
    )
    actual = values[test_indices]
    selected_predictions = np.asarray(test_predictions)
    metrics = {
        "model": selected_name,
        "mae_lkr": float(mean_absolute_error(actual, selected_predictions)),
        "rmse_lkr": float(np.sqrt(mean_squared_error(actual, selected_predictions))),
        "mape": float(np.mean(np.abs((actual - selected_predictions) / actual)) * 100),
        "train_start": str(dates.iloc[0].date()),
        "train_end": str(dates.iloc[split - 1].date()),
        "test_start": str(dates.iloc[split].date()),
        "test_end": str(dates.iloc[test_indices[-1]].date()),
        "latest_observation": str(dates.iloc[-1].date()),
        "future_horizon_months": HORIZON,
        "target": "monthly average auction price (LKR/kg)",
        "selection": "lowest RMSE across expanding rolling validation folds before 2025",
    }
    (DATA_DIR / "combined_auction_price_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({"name": selected_name, "model": final_model}, MODEL_DIR / "combined_auction_price_model.joblib")
    print(f"Selected {selected_name}; 2025 test MAE={metrics['mae_lkr']:.2f} LKR/kg, RMSE={metrics['rmse_lkr']:.2f} LKR/kg")


if __name__ == "__main__":
    main()
