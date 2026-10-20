"""Train an LSTM export-volume forecaster with chronological evaluation."""
import json
import random
from pathlib import Path

import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow.keras import Sequential
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from tensorflow.keras.layers import Dense, Dropout, Input, LSTM


ML_DIR = Path(__file__).resolve().parents[2]
RAW_FILE = ML_DIR / "datasets" / "raw" / "component04" / "Tea_Export_Demand_Forecast_Dataset.xlsx"
DATA_DIR = ML_DIR / "datasets" / "processed" / "component04"
MODEL_DIR = ML_DIR / "models" / "component04"
HORIZON = 12
LOOKBACKS = (6, 12)
UNIT_OPTIONS = (16, 32)
MAX_EPOCHS = 150
SEED = 42


def read_history() -> pd.DataFrame:
    df = pd.read_excel(RAW_FILE, sheet_name="Monthly_History")
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Export_Volume_KG"] = pd.to_numeric(df["Export_Volume_KG"], errors="coerce")
    df = df.dropna(subset=["Date", "Export_Volume_KG"]).sort_values("Date")
    monthly = df[["Date", "Export_Volume_KG"]].drop_duplicates("Date").rename(
        columns={"Date": "date", "Export_Volume_KG": "export_volume_kg"}
    ).reset_index(drop=True)
    expected = pd.date_range(monthly.date.min(), monthly.date.max(), freq="MS")
    if len(monthly) != 120 or not pd.DatetimeIndex(monthly.date).equals(expected):
        raise ValueError("Expected a complete 120-month monthly history (2016-01 through 2025-12).")
    if (monthly.export_volume_kg <= 0).any():
        raise ValueError("Export volumes must be positive before log/scale forecasting.")
    return monthly


def scale_fit(values: np.ndarray):
    low, high = float(np.min(values)), float(np.max(values))
    if high <= low:
        raise ValueError("Cannot scale a constant export volume series.")
    return low, high


def scale_values(values: np.ndarray, low: float, high: float) -> np.ndarray:
    return ((values - low) / (high - low)).astype(np.float32)


def inverse_scale(value: float, low: float, high: float) -> float:
    return float(value * (high - low) + low)


def season_features(date: pd.Timestamp) -> tuple[float, float]:
    angle = 2 * np.pi * (pd.Timestamp(date).month - 1) / 12
    return float(np.sin(angle)), float(np.cos(angle))


def sequences(scaled: np.ndarray, dates: pd.Series, lookback: int):
    X, y, target_indices = [], [], []
    for i in range(lookback, len(scaled)):
        sin_month, cos_month = season_features(pd.Timestamp(dates.iloc[i]))
        X.append(np.column_stack((scaled[i - lookback:i],
                                  np.full(lookback, sin_month),
                                  np.full(lookback, cos_month))))
        y.append(scaled[i])
        target_indices.append(i)
    return np.asarray(X, dtype=np.float32), np.asarray(y, dtype=np.float32), np.asarray(target_indices)


def build_model(lookback: int, units: int, seed: int):
    tf.keras.backend.clear_session()
    tf.keras.utils.set_random_seed(seed)
    model = Sequential([
        Input(shape=(lookback, 3)),
        LSTM(units, return_sequences=True),
        Dropout(0.20),
        LSTM(max(8, units // 2)),
        Dropout(0.15),
        Dense(16, activation="relu"),
        Dense(1),
    ])
    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=0.001), loss="mse")
    return model


def fit_with_validation(model, X_train, y_train, X_val, y_val, epochs=MAX_EPOCHS):
    callbacks = [
        EarlyStopping(monitor="val_loss", patience=18, restore_best_weights=True),
        ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=7, min_lr=1e-5),
    ]
    history = model.fit(
        X_train, y_train, validation_data=(X_val, y_val), epochs=epochs,
        batch_size=8, shuffle=False, callbacks=callbacks, verbose=0,
    )
    return int(np.argmin(history.history["val_loss"]) + 1)


def recursive_forecast(model, history_scaled: list[float], dates: pd.DatetimeIndex, lookback: int):
    history = list(history_scaled)
    result = []
    for date in dates:
        sin_month, cos_month = season_features(date)
        x = np.column_stack((np.asarray(history[-lookback:]),
                             np.full(lookback, sin_month),
                             np.full(lookback, cos_month))).astype(np.float32)[None, ...]
        value = float(model.predict(x, verbose=0)[0, 0])
        result.append(value)
        history.append(value)
    return np.asarray(result)


def score(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    error = actual - predicted
    return {
        "mae_kg": float(np.mean(np.abs(error))),
        "rmse_kg": float(np.sqrt(np.mean(error**2))),
        "mape": float(np.mean(np.abs(error / actual)) * 100),
    }


def main() -> None:
    random.seed(SEED)
    np.random.seed(SEED)
    tf.keras.utils.set_random_seed(SEED)
    monthly = read_history()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    monthly.to_csv(DATA_DIR / "export_demand_monthly.csv", index=False)

    values = monthly.export_volume_kg.to_numpy(dtype=np.float64)
    dates = monthly.date.reset_index(drop=True)
    # Validation: 2016-2023 train, recursively forecast all 12 months of 2024.
    validation_start = 96
    validation_end = 108
    validation_dates = pd.DatetimeIndex(dates.iloc[validation_start:validation_end])
    configs = []
    for lookback in LOOKBACKS:
        for units in UNIT_OPTIONS:
            low, high = scale_fit(values[:validation_start])
            scaled_all = scale_values(values[:validation_end], low, high)
            X_all, y_all, indices = sequences(scaled_all, dates.iloc[:validation_end].reset_index(drop=True), lookback)
            train_mask = indices < validation_start
            val_mask = indices >= validation_start
            model = build_model(lookback, units, SEED + lookback + units)
            best_epoch = fit_with_validation(model, X_all[train_mask], y_all[train_mask], X_all[val_mask], y_all[val_mask])
            val_pred_scaled = recursive_forecast(model, list(scaled_all[:validation_start]), validation_dates, lookback)
            val_pred = np.asarray([inverse_scale(float(value), low, high) for value in val_pred_scaled])
            metrics = score(values[validation_start:validation_end], val_pred)
            configs.append({"lookback_months": lookback, "units": units, "best_epochs": best_epoch,
                            "validation_mae_kg": metrics["mae_kg"], "validation_rmse_kg": metrics["rmse_kg"],
                            "validation_mape": metrics["mape"]})
            print(f"LSTM lookback={lookback}, units={units}, validation RMSE={metrics['rmse_kg']:.0f} kg")
    best = min(configs, key=lambda row: row["validation_rmse_kg"])
    lookback, units, epochs = best["lookback_months"], best["units"], best["best_epochs"]

    # Final chronological test: train through 2024, recursively forecast 2025.
    test_start = 108
    test_end = 120
    test_dates = pd.DatetimeIndex(dates.iloc[test_start:test_end])
    low, high = scale_fit(values[:test_start])
    scaled_train = scale_values(values[:test_start], low, high)
    X_train, y_train, _ = sequences(scaled_train, dates.iloc[:test_start].reset_index(drop=True), lookback)
    actual = values[test_start:test_end]
    test_results = []
    test_predictions_by_config = {}
    for config_index, config in enumerate(configs):
        config_lookback = config["lookback_months"]
        config_low, config_high = scale_fit(values[:test_start])
        config_scaled = scale_values(values[:test_start], config_low, config_high)
        config_X, config_y, _ = sequences(config_scaled, dates.iloc[:test_start].reset_index(drop=True), config_lookback)
        test_model = build_model(config_lookback, config["units"], SEED + 100 + config_index)
        test_model.fit(config_X, config_y, epochs=config["best_epochs"], batch_size=8, shuffle=False, verbose=0)
        prediction_scaled = recursive_forecast(test_model, list(config_scaled), test_dates, config_lookback)
        predictions = np.asarray([inverse_scale(float(value), config_low, config_high) for value in prediction_scaled])
        test_predictions_by_config[(config_lookback, config["units"])] = predictions
        test_result = score(actual, predictions)
        config.update({"test_mae_kg": test_result["mae_kg"], "test_rmse_kg": test_result["rmse_kg"], "test_mape": test_result["mape"]})
        test_results.append(test_result)
    selected_key = (lookback, units)
    test_predictions = test_predictions_by_config[selected_key]
    test_metrics = test_results[configs.index(best)]
    pd.DataFrame({"date": test_dates, "actual_export_volume_kg": actual,
                  "predicted_export_volume_kg": test_predictions}).to_csv(
        DATA_DIR / "export_demand_test_predictions.csv", index=False
    )

    # Refit the selected LSTM config on every observed month for the 2026 forecast.
    final_low, final_high = scale_fit(values)
    final_scaled = scale_values(values, final_low, final_high)
    X_full, y_full, _ = sequences(final_scaled, dates, lookback)
    final_model = build_model(lookback, units, SEED + 200)
    final_model.fit(X_full, y_full, epochs=epochs, batch_size=8, shuffle=False, verbose=0)
    future_dates = pd.date_range(dates.iloc[-1] + pd.offsets.MonthBegin(1), periods=HORIZON, freq="MS")
    future_scaled = recursive_forecast(final_model, list(final_scaled), future_dates, lookback)
    future = [inverse_scale(float(value), final_low, final_high) for value in future_scaled]
    pd.DataFrame({"date": future_dates, "forecast_export_volume_kg": future}).to_csv(
        DATA_DIR / "export_demand_forecast.csv", index=False
    )

    comparison = pd.DataFrame([
        {"model": f"LSTM (lookback={row['lookback_months']}, units={row['units']})",
         "validation_mae_kg": row["validation_mae_kg"], "validation_rmse_kg": row["validation_rmse_kg"],
         "validation_months": 12, "test_mae_kg": row["test_mae_kg"], "test_rmse_kg": row["test_rmse_kg"]}
        for row in configs
    ])
    comparison.to_csv(DATA_DIR / "export_demand_model_comparison.csv", index=False)
    metadata = {
        **test_metrics,
        "model": f"LSTM (lookback={lookback}, units={units})",
        "lookback_months": lookback,
        "units": units,
        "epochs": epochs,
        "train_months": test_start,
        "test_months": test_end - test_start,
        "train_start": str(dates.iloc[0].date()),
        "train_end": str(dates.iloc[test_start - 1].date()),
        "test_start": str(dates.iloc[test_start].date()),
        "test_end": str(dates.iloc[test_end - 1].date()),
        "validation_start": str(dates.iloc[validation_start].date()),
        "validation_end": str(dates.iloc[validation_end - 1].date()),
        "latest_observation": str(dates.iloc[-1].date()),
        "forecast_horizon_months": HORIZON,
        "framework": f"TensorFlow {tf.__version__}",
        "prediction_strategy": "recursive 12-month forecast",
        "feature_columns": ["lagged_export_volume_kg", "target_month_sin", "target_month_cos"],
        "validation_candidates": configs,
    }
    (DATA_DIR / "export_demand_metrics.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    final_model.save(MODEL_DIR / "export_demand_lstm.keras")
    (MODEL_DIR / "export_demand_lstm_scaler.json").write_text(
        json.dumps({"min": final_low, "max": final_high}), encoding="utf-8"
    )
    print(f"Selected LSTM lookback={lookback}, units={units}; 2025 recursive test MAE={test_metrics['mae_kg']:.0f} kg, RMSE={test_metrics['rmse_kg']:.0f} kg, MAPE={test_metrics['mape']:.2f}%")


if __name__ == "__main__":
    main()
