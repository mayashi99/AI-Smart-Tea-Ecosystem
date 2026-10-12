"""Leakage-safe monthly auction-price modelling pipeline.

The test prediction is a one-step-ahead walk-forward prediction: each month is
predicted using only prices available before that month.  This is deliberately
different from a recursive future forecast, whose errors compound by design.
"""
import json
import os
import random
from dataclasses import asdict, dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import MinMaxScaler

try:
    import tensorflow as tf
    from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint, ReduceLROnPlateau
    from tensorflow.keras.layers import Bidirectional, Dense, Dropout, GRU, Input, LSTM
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.optimizers import Adam
except ImportError:  # The deterministic fallback keeps the API usable in lightweight installs.
    tf = None

SEED = 42
TARGET, ZONE_COLUMN, DATE_COLUMN = "avg_price_lkr", "growing_zone", "auction_date"
BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR, MODEL_DIR = BASE_DIR / "datasets" / "processed" / "component04", BASE_DIR / "models" / "component04"
TRAIN_FILE, TEST_FILE = DATA_DIR / "auction_price_lstm_train.csv", DATA_DIR / "auction_price_lstm_test.csv"
PREDICTIONS_FILE, METRICS_FILE = DATA_DIR / "auction_price_lstm_predictions.csv", DATA_DIR / "auction_price_lstm_metrics.csv"
FORECAST_FILE, TEST_COMPARISON_FILE = DATA_DIR / "auction_price_lstm_future_forecast.csv", DATA_DIR / "auction_price_lstm_test_comparison.csv"
MODEL_INFO_FILE = MODEL_DIR / "auction_lstm_model_info.json"
FUTURE_MONTHS, VALIDATION_MONTHS = 12, 24


@dataclass(frozen=True)
class ModelConfig:
    model_type: str
    lookback: int
    units: int
    dropout: float
    learning_rate: float
    batch_size: int
    epochs: int = 100


# A compact time-series validation search: every requested lookback is tested,
# and units, learning rate, batch size, and recurrent architecture vary too.
SEARCH_CONFIGS = (
    ModelConfig("lstm", 12, 32, .15, 1e-3, 8),
    ModelConfig("lstm", 24, 64, .20, 5e-4, 8),
    ModelConfig("lstm", 36, 96, .25, 3e-4, 16),
    ModelConfig("gru", 24, 64, .20, 5e-4, 8),
    ModelConfig("bilstm", 24, 48, .20, 5e-4, 8),
)
LOOKBACK_MONTHS, HIDDEN_SIZE, EPOCHS = 24, 64, 100  # backwards-compatible public defaults


def set_seed() -> None:
    random.seed(SEED); np.random.seed(SEED)
    if tf is not None:
        tf.keras.utils.set_random_seed(SEED)


def load_dataset(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df[DATE_COLUMN] = pd.to_datetime(df[DATE_COLUMN], errors="coerce")
    df[TARGET] = pd.to_numeric(df[TARGET], errors="coerce")
    missing = df[[DATE_COLUMN, ZONE_COLUMN, TARGET]].isna().sum()
    if missing.any():
        print(f"{path.name}: dropping rows with missing required values: {missing.to_dict()}")
    return df.dropna(subset=[DATE_COLUMN, ZONE_COLUMN, TARGET]).sort_values([ZONE_COLUMN, DATE_COLUMN]).reset_index(drop=True)


def create_scaler() -> MinMaxScaler:
    return MinMaxScaler(feature_range=(0, 1))


def calendar_features(dates: pd.Series) -> np.ndarray:
    months = pd.to_datetime(dates).dt.month.to_numpy()
    angle = 2 * np.pi * (months - 1) / 12
    return np.column_stack((np.sin(angle), np.cos(angle)))


def make_supervised(scaled_values: np.ndarray, dates: pd.Series, lookback: int) -> tuple[np.ndarray, np.ndarray]:
    """Lag-price windows plus seasonal sin/cos for the predicted month."""
    if len(scaled_values) <= lookback:
        raise ValueError(f"Need at least {lookback + 1} observations, got {len(scaled_values)}")
    seasonal = calendar_features(dates)
    X = [np.column_stack((scaled_values[i - lookback:i], np.tile(seasonal[i], (lookback, 1)))) for i in range(lookback, len(scaled_values))]
    return np.asarray(X, dtype=np.float32), np.asarray(scaled_values[lookback:], dtype=np.float32)


def build_windows(values: np.ndarray, lookback: int):
    """Legacy helper retained for callers/tests that use price-only windows."""
    dates = pd.Series(pd.date_range("2000-01-01", periods=len(values), freq="MS"))
    return make_supervised(np.asarray(values, dtype=float), dates, lookback)


class NumpyLSTMRegressor:
    """Ridge fallback when TensorFlow is not installed (not presented as an LSTM)."""
    def __init__(self, hidden_size: int = HIDDEN_SIZE, learning_rate: float = .001):
        self.model = Ridge(alpha=1.0)
    def fit(self, X_train, y_train, epochs: int = EPOCHS, verbose: bool = False, **_):
        self.model.fit(np.asarray(X_train).reshape(len(X_train), -1), y_train)
        if verbose:
            for epoch in range(epochs):
                print(f"Epoch {epoch + 1}/{epochs} - fallback ridge fit complete")
    def predict(self, X, verbose=0):
        return self.model.predict(np.asarray(X).reshape(len(X), -1)).reshape(-1, 1)


class KerasLSTMRegressor:
    def __init__(self, config: ModelConfig | None = None, checkpoint: Path | None = None,
                 lookback: int = LOOKBACK_MONTHS, hidden_size: int = HIDDEN_SIZE):
        # lookback/hidden_size preserve the small public API used by older callers.
        self.config = config or ModelConfig("lstm", lookback, hidden_size, .20, 1e-3, 8)
        self.checkpoint, self.model = checkpoint or MODEL_DIR / "temporary_best.keras", None
    def build_model(self):
        recurrent = {"lstm": LSTM, "gru": GRU}[self.config.model_type] if self.config.model_type != "bilstm" else LSTM
        first = recurrent(self.config.units, return_sequences=True)
        if self.config.model_type == "bilstm": first = Bidirectional(first)
        self.model = Sequential([Input(shape=(self.config.lookback, 3)), first, Dropout(self.config.dropout), recurrent(max(16, self.config.units // 2)), Dropout(self.config.dropout), Dense(32, activation="relu"), Dense(1)])
        self.model.compile(optimizer=Adam(learning_rate=self.config.learning_rate), loss="mse")
    def fit(self, X_train, y_train, X_val=None, y_val=None):
        if len(X_train) != len(y_train):
            raise ValueError("Training input/output size mismatch.")
        if self.model is None: self.build_model()
        if X_val is None or y_val is None:
            X_val, y_val = X_train, y_train
        callbacks = [EarlyStopping(monitor="val_loss", patience=15, restore_best_weights=True), ReduceLROnPlateau(monitor="val_loss", factor=.5, patience=6, min_lr=1e-5), ModelCheckpoint(self.checkpoint, monitor="val_loss", save_best_only=True)]
        self.model.fit(X_train, y_train, validation_data=(X_val, y_val), epochs=self.config.epochs, batch_size=self.config.batch_size, shuffle=False, callbacks=callbacks, verbose=0)
    def predict(self, X, verbose=0): return self.model.predict(X, verbose=verbose)
    def save(self, path: Path): self.model.save(path)


def build_regressor(config: ModelConfig, checkpoint: Path):
    return (KerasLSTMRegressor(config, checkpoint), "keras") if tf is not None else (NumpyLSTMRegressor(), "sklearn_ridge_fallback")


def metrics(y_true, y_pred) -> dict[str, float]:
    y_true, y_pred = np.asarray(y_true, float), np.asarray(y_pred, float)
    nonzero = y_true != 0
    return {"mae": float(mean_absolute_error(y_true, y_pred)), "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))), "mape": float(np.mean(np.abs((y_true[nonzero] - y_pred[nonzero]) / y_true[nonzero])) * 100), "r2": float(r2_score(y_true, y_pred))}


def _fit_for_validation(values: np.ndarray, dates: pd.Series, config: ModelConfig, name: str) -> tuple[object, MinMaxScaler, np.ndarray, np.ndarray]:
    cut = len(values) - min(VALIDATION_MONTHS, max(config.lookback + 6, len(values) // 5))
    fit_values, val_values = values[:cut], values[cut:]
    scaler = create_scaler(); fit_scaled = scaler.fit_transform(fit_values.reshape(-1, 1)).ravel()
    X_fit, y_fit = make_supervised(fit_scaled, dates.iloc[:cut], config.lookback)
    all_scaled = scaler.transform(values.reshape(-1, 1)).ravel()
    X_all, y_all = make_supervised(all_scaled, dates, config.lookback)
    val_start = cut - config.lookback
    checkpoint = MODEL_DIR / f"{name}_validation.keras"
    model, _ = build_regressor(config, checkpoint)
    if tf is not None: model.fit(X_fit, y_fit, X_all[val_start:], y_all[val_start:])
    else: model.fit(X_fit, y_fit)
    pred = scaler.inverse_transform(model.predict(X_all[val_start:])).ravel()
    # Validation checkpoints are temporary; only final per-zone models are artifacts.
    checkpoint.unlink(missing_ok=True)
    return model, scaler, val_values, pred


def select_config(values: np.ndarray, dates: pd.Series, zone: str) -> tuple[ModelConfig, list[dict]]:
    results = []
    candidates = SEARCH_CONFIGS if tf is not None else SEARCH_CONFIGS[:3]
    for i, config in enumerate(candidates):
        _, _, actual, pred = _fit_for_validation(values, dates, config, f"{zone.replace(' ', '_')}_{i}")
        result = {**asdict(config), **metrics(actual, pred)}; results.append(result)
    best = min(results, key=lambda row: row["rmse"])
    return ModelConfig(**{key: best[key] for key in ModelConfig.__dataclass_fields__}), results


def fit_final(values: np.ndarray, dates: pd.Series, config: ModelConfig, zone: str):
    scaler = create_scaler(); scaled = scaler.fit_transform(values.reshape(-1, 1)).ravel()  # training rows only
    X, y = make_supervised(scaled, dates, config.lookback)
    model, framework = build_regressor(config, MODEL_DIR / f"{zone.replace(' ', '_')}_best.keras")
    split = max(1, len(X) - min(VALIDATION_MONTHS, max(6, len(X) // 5)))
    if tf is not None: model.fit(X[:split], y[:split], X[split:], y[split:]); model.save(MODEL_DIR / f"{zone.replace(' ', '_')}_best.keras")
    else: model.fit(X, y); joblib.dump(model, MODEL_DIR / f"{zone.replace(' ', '_')}_best.joblib")
    joblib.dump(scaler, MODEL_DIR / f"{zone.replace(' ', '_')}_scaler.joblib")
    return model, scaler, framework, scaled


def one_step_predict(model, scaler, history_scaled, prediction_dates: pd.Series, actual_values: np.ndarray, lookback: int) -> np.ndarray:
    history = list(history_scaled); predictions = []
    # Actual is appended only *after* its prediction, preventing target leakage.
    for date, actual in zip(prediction_dates, actual_values):
        season = calendar_features(pd.Series([date]))[0]
        x = np.column_stack((np.asarray(history[-lookback:]), np.tile(season, (lookback, 1))))[None, ...]
        pred_scaled = model.predict(x, verbose=0)[0, 0]
        predictions.append(pred_scaled)
        history.append(scaler.transform([[actual]])[0, 0])
    return scaler.inverse_transform(np.asarray(predictions).reshape(-1, 1)).ravel()


def future_predict(model, scaler, history_scaled, last_date, lookback: int) -> tuple[pd.DatetimeIndex, np.ndarray]:
    dates = pd.date_range(pd.Timestamp(last_date) + pd.offsets.MonthBegin(1), periods=FUTURE_MONTHS, freq="MS")
    history, predictions = list(history_scaled), []
    for date in dates:
        season = calendar_features(pd.Series([date]))[0]
        x = np.column_stack((np.asarray(history[-lookback:]), np.tile(season, (lookback, 1))))[None, ...]
        value = model.predict(x, verbose=0)[0, 0]; predictions.append(value); history.append(value)
    return dates, scaler.inverse_transform(np.asarray(predictions).reshape(-1, 1)).ravel()


def prepare_test_comparison_data(predictions_df):
    return predictions_df[["growing_zone", "auction_date", "actual_avg_price_lkr", "lstm_predicted_avg_price_lkr"]].copy()


def get_model_config():
    return {"framework": "keras" if tf is not None else "sklearn_ridge_fallback", "lookback_months": LOOKBACK_MONTHS, "hidden_size": HIDDEN_SIZE, "epochs": EPOCHS, "recursive_prediction": False, "features": ["lagged_price", "month_sin", "month_cos"]}


def main():
    set_seed(); os.makedirs(MODEL_DIR, exist_ok=True)
    train_df, test_df = load_dataset(TRAIN_FILE), load_dataset(TEST_FILE)
    prediction_parts, forecast_parts, metric_rows, model_info = [], [], [], {}
    for zone in sorted(train_df[ZONE_COLUMN].unique()):
        tr = train_df[train_df[ZONE_COLUMN].eq(zone)].sort_values(DATE_COLUMN).reset_index(drop=True)
        te = test_df[test_df[ZONE_COLUMN].eq(zone)].sort_values(DATE_COLUMN).reset_index(drop=True)
        values = tr[TARGET].to_numpy(float)
        config, tuning = select_config(values, tr[DATE_COLUMN], zone)
        model, scaler, framework, scaled = fit_final(values, tr[DATE_COLUMN], config, zone)
        pred = one_step_predict(model, scaler, scaled, te[DATE_COLUMN], te[TARGET].to_numpy(float), config.lookback)
        score = metrics(te[TARGET], pred)
        future_dates, future = future_predict(model, scaler, list(scaled) + list(scaler.transform(te[[TARGET]]).ravel()), te[DATE_COLUMN].max(), config.lookback)
        prediction_parts.append(pd.DataFrame({"growing_zone": zone, "auction_date": te[DATE_COLUMN], "actual_avg_price_lkr": te[TARGET], "lstm_predicted_avg_price_lkr": pred}))
        forecast_parts.append(pd.DataFrame({"growing_zone": zone, "auction_date": future_dates, "lstm_forecast_avg_price_lkr": future}))
        row = {"growing_zone": zone, "model": "LSTM" if framework == "keras" else "Ridge fallback", "framework": framework, "lookback_months": config.lookback, "hidden_size": config.units, "epochs": config.epochs, "batch_size": config.batch_size, "learning_rate": config.learning_rate, "model_type": config.model_type, "features": "lagged_price,month_sin,month_cos", "train_rows": len(tr), "test_rows": len(te), "prediction_strategy": "one_step_walk_forward", **score}
        metric_rows.append(row); model_info[zone] = {**row, "validation_candidates": tuning}
        print(f"{zone}: {framework}, {config.model_type}/{config.lookback}m RMSE={score['rmse']:.2f}, MAE={score['mae']:.2f}, R2={score['r2']:.3f}")
    predictions = pd.concat(prediction_parts, ignore_index=True); forecasts = pd.concat(forecast_parts, ignore_index=True)
    predictions.to_csv(PREDICTIONS_FILE, index=False); prepare_test_comparison_data(predictions).to_csv(TEST_COMPARISON_FILE, index=False); forecasts.to_csv(FORECAST_FILE, index=False); pd.DataFrame(metric_rows).to_csv(METRICS_FILE, index=False)
    MODEL_INFO_FILE.write_text(json.dumps(model_info, indent=2), encoding="utf-8")


if __name__ == "__main__": main()
