# Component 02 — Expected Yield XGBoost artifact

Model name: **`xgboost_yield.joblib`**

This directory stores the trained, versioned XGBoost `Pipeline` artifact:

- `xgboost_yield.joblib` — the fitted preprocessing pipeline and `XGBRegressor`.
- `validation_metrics.json` — MAE, RMSE, R² and MAPE calculated on the 2024 validation set.

Do not serialize only the regressor: the saved pipeline also contains median imputation and one-hot encoding for `Location` and `Grown_Type`. This ensures inference uses exactly the transformations fitted during training.

Create the artifact after placing the input CSV at
`backend/ml/datasets/raw/component02/expected_yield_prediction/expected_yield.csv`:

```bash
cd backend
python -m ml.preprocessing.component02.expected_yield_prediction.split_dataset
python -m ml.training.component02.expected_yield_prediction.xgboost.xgboost_train
python -m ml.training.component02.expected_yield_prediction.xgboost.xgboost_evaluate
```

The source requires these input fields: `Year`, `Month_Number`, `Week_Number`, `Temperature`, `Rainfall_mm`, `Humidity`, `Wind_Speed`, `Solar_Radiation`, `Location`, `Grown_Type`; prediction target: `kg_per_Acre`.
