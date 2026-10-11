# AI Smart Tea Ecosystem

AI-powered smart tea ecosystem for the Sri Lankan tea industry.

## Component 04: Auction Price Forecasting

This project now uses an LSTM-only model for tea auction price forecasting. The old ARIMA and ARIMA + LSTM hybrid artifacts were removed.

### Current LSTM Output

The pipeline trains one LSTM model per growing zone:

| Growing zone | MAE | RMSE | Train period | Test period |
| --- | ---: | ---: | --- | --- |
| High Growns | 203.85 | 270.33 | Sep 2011 - Jun 2023 | Jul 2023 - May 2026 |
| Low Growns | 961.83 | 1128.91 | Sep 2011 - Jun 2023 | Jul 2023 - May 2026 |
| Medium Growns | 488.82 | 593.72 | Sep 2011 - May 2023 | Jun 2023 - May 2026 |
| Total | 267.82 | 342.54 | Sep 2011 - May 2023 | Jun 2023 - May 2026 |

Model setup:

- Framework: TensorFlow/Keras LSTM when available, otherwise a NumPy fallback trainer
- Lookback: 12 months
- Hidden size: 128
- Epochs: 200
- Recursive prediction: enabled for multi-step forecasting
- Forecast horizon: 12 months

### Generated Files

Processed data:

- `backend/ml/datasets/processed/component04/auction_price_clean.csv`
- `backend/ml/datasets/processed/component04/auction_price_lstm.csv`
- `backend/ml/datasets/processed/component04/auction_price_lstm_train.csv`
- `backend/ml/datasets/processed/component04/auction_price_lstm_test.csv`
- `backend/ml/datasets/processed/component04/auction_price_lstm_predictions.csv`
- `backend/ml/datasets/processed/component04/auction_price_lstm_future_forecast.csv`
- `backend/ml/datasets/processed/component04/auction_price_lstm_metrics.csv`

## Component 04: Export Demand Forecasting

The export workbook at `backend/ml/datasets/raw/component04/Exports Volume 2016-2025 10 yrs .xlsx`
is aggregated into monthly total export volume (kg). Ridge, tree-based, and boosting models are
compared; the current model is selected by 2025 one-step walk-forward RMSE and then retrained on all
available months before forecasting the next 12 months. This is an aggregate demand forecast; it
does not split results by country, tea process, or package. Since 2025 is used for model selection,
its reported test accuracy is a selection score rather than an independent final estimate.

### Train Again

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m backend.ml.training.component04.train_export_demand
```

Generated files are in `backend/ml/datasets/processed/component04/`:

- `export_demand_monthly.csv`
- `export_demand_test_predictions.csv`
- `export_demand_forecast.csv`
- `export_demand_metrics.json`

The API endpoint is `/api/component04/export-demand`. The frontend provides a separate Export Demand
page at `/export-demand`; the Auction Price page remains at `/`.

### Combined Workbook Auction Price Forecast

`backend/ml/datasets/raw/component04/Combined_Sales_Quantity_and_Price_Single_Sheet_2016_2026.xlsx`
contains weekly rows with repeated monthly price aggregates. The pipeline keeps one monthly average
price per month, compares baselines and ML regressors using rolling validation through 2024, tests on
2025, and refits the selected model through the latest available month for a 12-month forecast.

```powershell
.\.venv\Scripts\python.exe -m backend.ml.training.component04.train_combined_auction_price
```

The API endpoint is `/api/component04/combined-auction-price`; its chart and test predictions appear
on the Auction Price page.

Model:

- `backend/ml/models/component04/auction_lstm.joblib`

### Train Again

```powershell
cd backend
.\.venv\Scripts\python.exe ml\preprocessing\component04\clean_auction_data.py
.\.venv\Scripts\python.exe ml\training\component04\train_lstm.py
```

### Run Backend

```powershell
cd backend
.\.venv\Scripts\python.exe run.py
```

.\.venv\Scripts\python.exe -m backend.ml.training.component04.train_export_demand



API endpoint:

- `http://127.0.0.1:8000/api/component04/train-output`

### Run Dashboard

```powershell
cd frontend
npm run dev
```

Open the Vite URL shown in the terminal, usually:

- `http://localhost:5173`
