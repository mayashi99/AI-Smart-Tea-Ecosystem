import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


def load_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "training"
        / "component04"
        / "usd_forecasting"
        / "compare_models.py"
    )
    spec = importlib.util.spec_from_file_location("usd_forecast_compare", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_load_history_sorts_and_filters_usd_rows(tmp_path):
    module = load_module()
    source = tmp_path / "rates.csv"
    dates = pd.bdate_range("2024-01-01", periods=65)
    pd.DataFrame({
        "Currency": ["USD"] * len(dates) + ["EUR"],
        "Date": list(dates[::-1].strftime("%Y-%m-%d")) + ["2024-01-01"],
        "Exchange Rate": list(range(300, 300 + len(dates))) + [1.1],
    }).to_csv(source, index=False)

    loaded = module.load_history(source)

    assert loaded["Date"].is_monotonic_increasing
    assert len(loaded) == len(dates)
    assert loaded["Exchange Rate"].iloc[0] == 364
    assert loaded["Exchange Rate"].iloc[-1] == 300


def test_compare_models_writes_model_folders_and_forecast_outputs(tmp_path):
    module = load_module()
    source = tmp_path / "rates.csv"
    output_dir = tmp_path / "processed"
    model_dir = tmp_path / "models"
    dates = pd.bdate_range("2022-01-03", periods=180)
    values = 300 + np.arange(len(dates)) * 0.08 + np.sin(np.arange(len(dates)) / 8)
    pd.DataFrame({
        "Currency": "USD",
        "Date": dates.strftime("%Y-%m-%d"),
        "Exchange Rate": values,
    }).to_csv(source, index=False)

    comparison = module.compare_models(source, output_dir, model_dir, horizon=5)

    assert set(comparison["model"]) == {"ridge", "extra_trees"}
    assert comparison["rank"].tolist() == [1, 2]
    assert len(pd.read_csv(output_dir / "forecast_comparison.csv")) == 5
    for name in module.MODEL_FACTORIES:
        assert (output_dir / name / "forecast.csv").exists()
        assert (output_dir / name / "validation_predictions.csv").exists()
        assert (output_dir / name / "test_predictions.csv").exists()
        assert (model_dir / name / "model.joblib").exists()
