# AI Smart Tea Ecosystem

AI-powered smart tea ecosystem for the Sri Lankan tea industry.

## Component 04

The Component 04 dashboard has three pages:

- `/` — auction price forecasts, including the combined sales-and-price workbook
- `/export-demand` — LSTM monthly tea export-volume forecast
- `/export-advisor` — RAG-grounded, explainable export planning recommendations
- `/export-readiness` — evidence-based Export Readiness Index (ERI)
- `/digital-passport` — tea batch traceability passport and ledger verification

The Export Advisor retrieves evidence from the forecast metrics, monthly history, and local planning
guides. It shows the sources and evidence IDs behind every recommendation. Without an LLM endpoint it
uses the same evidence with explainable rules; with an OpenAI-compatible endpoint it adds LLM synthesis.
Copy `backend/.env.example` settings to `backend/.env` and configure `LLM_API_BASE_URL`, `LLM_MODEL`,
and optionally `LLM_API_KEY` to enable that synthesis. The project does not include an LLM key.

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

The export-volume model uses the monthly history in
`backend/ml/datasets/raw/component04/Tea_Export_Demand_Forecast_Dataset.xlsx`. The LSTM pipeline uses
2016-2023 for training, 2024 for recursive validation and configuration selection, and 2025 for a
recursive test. It then refits the selected LSTM on all 2016-2025 observations for the next 12 months.
The aggregate demand forecast does not split results by country, tea process, or package.

### Train Again

From the repository root:

```powershell
backend\.venv312\Scripts\python.exe -m backend.ml.training.component04.train_export_demand_lstm
```

Generated files are in `backend/ml/datasets/processed/component04/`:

- `export_demand_monthly.csv`
- `export_demand_test_predictions.csv`
- `export_demand_forecast.csv`
- `export_demand_metrics.json`

The API endpoint is `/api/component04/export-demand`. The frontend provides a separate Export Demand
page at `/export-demand`; the Auction Price page remains at `/`.

Advisor API: `POST /api/component04/export-advisor` with JSON such as:

```json
{
  "question": "How should we plan export volumes for the next 12 months?",
  "destination_country": null,
  "business_goal": "plan seasonal inventory"
}
```

### Export Readiness Index and Digital Passport

The ERI page combines export-demand forecast metrics with user-declared monthly capacity,
document checks, and quality-control readiness. Its weighted criteria and recommendations are
shown with the evidence used for each score. It is a planning aid, not an official certification
or destination-specific compliance assessment. API: `POST /api/component04/export-readiness`.

The Digital Passport page records batch events (collection, processing, quality checks, packing,
export, and receipt) in `backend/data/component04/passport_ledger.jsonl`. Every event includes the
previous record hash and its own SHA-256 hash; `GET /api/component04/digital-passports/verify`
checks the chain. This local prototype is tamper-evident but is not connected to a distributed
blockchain network. The ledger is gitignored because it can contain operational traceability data.

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

The separate growing-zone auction pipeline stores its model metadata in
`backend/ml/models/component04/auction_lstm_model_info.json`.

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

### Run Dashboard

```powershell
cd frontend
npm run dev
```

Open the Vite URL shown in the terminal, usually:

- `http://localhost:5173`
