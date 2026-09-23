import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


def load_train_module():
    module_path = Path(__file__).resolve().parents[1] / "training" / "component04" / "train_lstm.py"
    spec = importlib.util.spec_from_file_location("train_lstm", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_clean_module():
    module_path = Path(__file__).resolve().parents[1] / "preprocessing" / "component04" / "clean_auction_data.py"
    spec = importlib.util.spec_from_file_location("clean_auction_data", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_cleaning_module_builds_zone_rows_for_the_new_excel_schema():
    module = load_clean_module()

    raw_df = pd.DataFrame(
        {
            "auction_date": ["2020-01-01", "2020-02-01"],
            "auction_high_grown_quantity": [100.0, 120.0],
            "auction_medium_grown_quantity": [50.0, 60.0],
            "auction_low_grown_quantity": [20.0, 30.0],
            "total_quantity": [170.0, 210.0],
            "high_grown_avg_price": [400.0, 420.0],
            "medium_grown_avg_price": [350.0, 360.0],
            "low_grown_avg_price": [300.0, 310.0],
            "high_grown_rain": [100.0, 110.0],
            "medium_grown_rain": [90.0, 95.0],
            "low_grown_rain": [80.0, 85.0],
            "high_grown_temp": [25.0, 26.0],
            "medium_grown_temp": [24.0, 25.0],
            "low_grown_temp": [23.0, 24.0],
        }
    )

    prepared = module.build_zone_long_format(raw_df)

    assert {"High Growns", "Medium Growns", "Low Growns", "Total"}.issubset(
        set(prepared["growing_zone"])
    )
    assert prepared.loc[prepared["growing_zone"] == "Total", "avg_price_lkr"].notna().all()
    assert prepared.loc[prepared["growing_zone"] == "High Growns", "avg_price_lkr"].iloc[0] == 400.0


def test_numpy_lstm_fit_emits_epoch_progress(capsys):
    module = load_train_module()

    model = module.NumpyLSTMRegressor(hidden_size=4, learning_rate=0.01)
    model.fit(np.array([[0.1, 0.2, 0.3]]), np.array([0.4]), epochs=2, verbose=True)

    captured = capsys.readouterr()
    assert "epoch 1/2" in captured.out.lower()
    assert "epoch 2/2" in captured.out.lower()


def test_prepare_test_comparison_data_keeps_actual_and_predictions():
    module = load_train_module()

    predictions_df = pd.DataFrame(
        {
            "growing_zone": ["High Growns", "High Growns"],
            "auction_date": ["2024-01-01", "2024-02-01"],
            "actual_avg_price_lkr": [100.0, 110.0],
            "lstm_predicted_avg_price_lkr": [95.0, 108.0],
        }
    )

    comparison_df = module.prepare_test_comparison_data(predictions_df)

    assert list(comparison_df.columns) == [
        "growing_zone",
        "auction_date",
        "actual_avg_price_lkr",
        "lstm_predicted_avg_price_lkr",
    ]
    assert comparison_df.iloc[0]["actual_avg_price_lkr"] == 100.0
    assert comparison_df.iloc[1]["lstm_predicted_avg_price_lkr"] == 108.0


def test_training_config_exposes_lstm_parameters():
    module = load_train_module()

    config = module.get_model_config()

    assert config["framework"] in {"keras", "numpy"}
    assert config["hidden_size"] == module.HIDDEN_SIZE
    assert config["epochs"] == module.EPOCHS
    assert config["recursive_prediction"] is True


def test_minmax_scaler_is_available_without_tensorflow():
    module = load_train_module()

    scaler = module.MinMaxScaler()
    values = np.array([[1.0], [2.0], [3.0]], dtype=float)
    scaled = scaler.fit_transform(values)

    assert scaled.shape == values.shape


def test_build_windows_requires_enough_history():
    module = load_train_module()

    with pytest.raises(ValueError):
        module.build_windows(np.array([1.0, 2.0, 3.0]), 4)


def test_keras_lstm_regressor_rejects_mismatched_training_lengths(monkeypatch):
    module = load_train_module()

    class DummySequential:
        def __init__(self, layers):
            self.layers = layers

        def compile(self, *args, **kwargs):
            return None

        def fit(self, x_train, y_train, **kwargs):
            self.fit_args = (x_train, y_train, kwargs)

        def predict(self, sample, verbose=0):
            return np.array([[0.25]])

    monkeypatch.setattr(module, "Sequential", DummySequential)
    monkeypatch.setattr(module, "Input", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "LSTM", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "Dropout", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "Dense", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "Adam", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "EarlyStopping", lambda *args, **kwargs: None)

    model = module.KerasLSTMRegressor(lookback=3)

    with pytest.raises(ValueError):
        model.fit(np.array([[1.0, 2.0, 3.0]]), np.array([0.1, 0.2]))
