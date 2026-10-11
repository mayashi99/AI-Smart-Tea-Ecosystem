import json
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException


router = APIRouter(prefix="/api/component04", tags=["component04"])

ML_DIR = Path(__file__).resolve().parents[2] / "ml"
DATA_DIR = ML_DIR / "datasets" / "processed" / "component04"

METRICS_FILE = DATA_DIR / "auction_price_lstm_metrics.csv"
PREDICTIONS_FILE = DATA_DIR / "auction_price_lstm_predictions.csv"
FORECAST_FILE = DATA_DIR / "auction_price_lstm_future_forecast.csv"

TEST_COMPARISON_FILE = DATA_DIR / "auction_price_lstm_test_comparison.csv"

TRAIN_FILE = DATA_DIR / "auction_price_lstm_train.csv"
TEST_FILE = DATA_DIR / "auction_price_lstm_test.csv"
EXPORT_METRICS_FILE = DATA_DIR / "export_demand_metrics.json"
EXPORT_FORECAST_FILE = DATA_DIR / "export_demand_forecast.csv"
EXPORT_TEST_FILE = DATA_DIR / "export_demand_test_predictions.csv"
EXPORT_COMPARISON_FILE = DATA_DIR / "export_demand_model_comparison.csv"
COMBINED_PRICE_METRICS_FILE = DATA_DIR / "combined_auction_price_metrics.json"
COMBINED_PRICE_FORECAST_FILE = DATA_DIR / "combined_auction_price_forecast.csv"
COMBINED_PRICE_TEST_FILE = DATA_DIR / "combined_auction_price_test_predictions.csv"
COMBINED_PRICE_COMPARISON_FILE = DATA_DIR / "combined_auction_price_model_comparison.csv"

def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Missing file: {path.name}")
    return pd.read_csv(path)


@router.get("/train-output")
def get_train_output():
    metrics_df = read_csv(METRICS_FILE)
    predictions_df = read_csv(PREDICTIONS_FILE)
    forecast_df = read_csv(FORECAST_FILE)
    test_comparison_df = read_csv(TEST_COMPARISON_FILE)
    train_df = read_csv(TRAIN_FILE)
    test_df = read_csv(TEST_FILE)

    if metrics_df.empty:
        raise HTTPException(status_code=404, detail="Training metrics are empty")

    predictions_df["lstm_error"] = (
        predictions_df["actual_avg_price_lkr"]
        - predictions_df["lstm_predicted_avg_price_lkr"]
    ).round(2)
    predictions_df["lstm_absolute_error"] = predictions_df["lstm_error"].abs().round(2)
    predictions_df["lstm_error_percent"] = (
        predictions_df["lstm_absolute_error"]
        / predictions_df["actual_avg_price_lkr"].replace(0, pd.NA)
        * 100
    ).round(2)

    zones = sorted(metrics_df["growing_zone"].dropna().unique().tolist())
    default_zone = "Total" if "Total" in zones else zones[0]
    default_metrics_df = metrics_df[metrics_df["growing_zone"].eq(default_zone)]
    # One selected production model is written per zone; this supports the
    # explicitly labelled local fallback when TensorFlow is not installed.
    lstm_metric = default_metrics_df.iloc[0].to_dict()
    zone_periods = {}
    for zone in zones:
        zone_train_df = train_df[train_df["growing_zone"].eq(zone)]
        zone_test_df = test_df[test_df["growing_zone"].eq(zone)]
        zone_periods[zone] = {
            "train_start": zone_train_df["auction_date"].min(),
            "train_end": zone_train_df["auction_date"].max(),
            "test_start": zone_test_df["auction_date"].min(),
            "test_end": zone_test_df["auction_date"].max(),
        }

    return {
        "model": lstm_metric.get("model", "LSTM"),
        "default_zone": default_zone,
        "zones": zones,
        "metrics": {
            "mae": round(float(lstm_metric["mae"]), 2),
            "rmse": round(float(lstm_metric["rmse"]), 2),
            "mape": round(float(lstm_metric.get("mape", 0)), 2),
            "r2": round(float(lstm_metric.get("r2", 0)), 4),
            "train_rows": int(lstm_metric["train_rows"]),
            "test_rows": int(lstm_metric["test_rows"]),
        },
        "model_metrics": [
            {
                "growing_zone": row["growing_zone"],
                "model": row["model"],
                "lookback_months": int(row["lookback_months"]),
                "hidden_size": int(row["hidden_size"]),
                "epochs": int(row["epochs"]),
                "train_rows": int(row["train_rows"]),
                "test_rows": int(row["test_rows"]),
                "mae": round(float(row["mae"]), 2),
                "rmse": round(float(row["rmse"]), 2),
                "mape": round(float(row.get("mape", 0)), 2),
                "r2": round(float(row.get("r2", 0)), 4),
                "batch_size": int(row.get("batch_size", 0)),
                "learning_rate": float(row.get("learning_rate", 0)),
                "model_type": row.get("model_type", "lstm"),
                "prediction_strategy": row.get("prediction_strategy", "calibrated_lstm"),
            }
            for row in metrics_df.to_dict(orient="records")
        ],
        "best_test_model": "LSTM",
        "lstm": {
            "role": "Direct monthly auction price forecasting",
            "framework": lstm_metric.get("framework", "numpy"),
            "lookback_months": int(lstm_metric["lookback_months"]),
            "hidden_size": int(lstm_metric["hidden_size"]),
            "epochs": int(lstm_metric["epochs"]),
            "mape": round(float(lstm_metric.get("mape", 0)), 2),
            "r2": round(float(lstm_metric.get("r2", 0)), 4),
            "model_type": lstm_metric.get("model_type", "lstm"),
            "prediction_strategy": lstm_metric.get("prediction_strategy", "calibrated_lstm"),
            "recursive_prediction": str(lstm_metric.get("prediction_strategy", "")).startswith("recursive"),
        },
        "periods": {
            "train_start": train_df["auction_date"].min(),
            "train_end": train_df["auction_date"].max(),
            "test_start": test_df["auction_date"].min(),
            "test_end": test_df["auction_date"].max(),
        },
        "zone_periods": zone_periods,
        "predictions": predictions_df.round(2).to_dict(orient="records"),
        "test_comparison": test_comparison_df.round(2).to_dict(orient="records"),
        "future_forecast": forecast_df.round(2).to_dict(orient="records"),
    }


@router.get("/export-demand")
def get_export_demand():
    """Return monthly export volume history, holdout predictions, and forecast."""
    if not EXPORT_METRICS_FILE.exists():
        raise HTTPException(status_code=404, detail="Export demand model is not trained yet")
    try:
        metrics = json.loads(EXPORT_METRICS_FILE.read_text(encoding="utf-8"))
        forecast = read_csv(EXPORT_FORECAST_FILE)
        test_predictions = read_csv(EXPORT_TEST_FILE)
        model_comparison = read_csv(EXPORT_COMPARISON_FILE)
        monthly = read_csv(DATA_DIR / "export_demand_monthly.csv")
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"Could not read export demand outputs: {exc}") from exc
    return {
        "metrics": metrics,
        "history": monthly.to_dict(orient="records"),
        "test_predictions": test_predictions.to_dict(orient="records"),
        "model_comparison": model_comparison.to_dict(orient="records"),
        "forecast": forecast.to_dict(orient="records"),
    }


@router.get("/combined-auction-price")
def get_combined_auction_price():
    """Return best-model monthly price forecast from the combined workbook."""
    if not COMBINED_PRICE_METRICS_FILE.exists():
        raise HTTPException(status_code=404, detail="Combined auction price model is not trained yet")
    try:
        metrics = json.loads(COMBINED_PRICE_METRICS_FILE.read_text(encoding="utf-8"))
        return {
            "metrics": metrics,
            "history": read_csv(DATA_DIR / "combined_auction_price_monthly.csv").to_dict(orient="records"),
            "test_predictions": read_csv(COMBINED_PRICE_TEST_FILE).to_dict(orient="records"),
            "model_comparison": read_csv(COMBINED_PRICE_COMPARISON_FILE).to_dict(orient="records"),
            "forecast": read_csv(COMBINED_PRICE_FORECAST_FILE).to_dict(orient="records"),
        }
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"Could not read combined auction price outputs: {exc}") from exc
