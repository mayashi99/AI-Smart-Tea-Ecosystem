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

API endpoint:

- `http://127.0.0.1:8000/api/component04/train-output`

### Run Dashboard

```powershell
cd frontend
npm run dev
```

Open the Vite URL shown in the terminal, usually:

- `http://localhost:5173`
