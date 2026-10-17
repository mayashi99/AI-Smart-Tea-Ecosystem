
from pathlib import Path
import json
import warnings

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

warnings.filterwarnings("ignore")

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data" / "splits"
MODEL_DIR = BASE_DIR / "models"
OUTPUT_DIR = BASE_DIR / "outputs"

MODEL_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET = "kg_per_Acre"

FEATURES = [
    "Year", "Month_Number", "Week_Number",
    "Temperature", "Rainfall_mm", "Humidity",
    "Wind_Speed", "Solar_Radiation",
    "Location", "Grown_Type",
]

CAT_FEATURES = ["Location", "Grown_Type"]

train_df = pd.read_csv(DATA_DIR / "train.csv")
val_df = pd.read_csv(DATA_DIR / "validation.csv")

for name, df in [("train", train_df), ("validation", val_df)]:
    missing = set(FEATURES + [TARGET]) - set(df.columns)
    if missing:
        raise ValueError(f"{name}.csv missing columns: {sorted(missing)}")

X_train = train_df[FEATURES].copy()
y_train = train_df[TARGET].astype(float)

X_val = val_df[FEATURES].copy()
y_val = val_df[TARGET].astype(float)

# CatBoost handles categorical columns directly.
for col in CAT_FEATURES:
    X_train[col] = X_train[col].astype(str)
    X_val[col] = X_val[col].astype(str)

param_grid = [
    {"iterations": 300, "depth": 4, "learning_rate": 0.03, "l2_leaf_reg": 3},
    {"iterations": 500, "depth": 4, "learning_rate": 0.03, "l2_leaf_reg": 5},
    {"iterations": 500, "depth": 6, "learning_rate": 0.03, "l2_leaf_reg": 3},
    {"iterations": 700, "depth": 6, "learning_rate": 0.03, "l2_leaf_reg": 5},
    {"iterations": 500, "depth": 8, "learning_rate": 0.02, "l2_leaf_reg": 5},
    {"iterations": 700, "depth": 5, "learning_rate": 0.05, "l2_leaf_reg": 5},
]

results = []
best_model = None
best_params = None
best_mae = float("inf")

print("=" * 60)
print("CATBOOST HYPERPARAMETER TUNING")
print("=" * 60)
print(f"Training rows: {len(train_df)}")
print(f"Validation rows: {len(val_df)}")
print("Validation year: 2024")
print("Test year 2025 will not be used.\n")

for i, params in enumerate(param_grid, start=1):
    print(f"Experiment {i}/{len(param_grid)}: {params}")

    model = CatBoostRegressor(
        **params,
        loss_function="RMSE",
        eval_metric="MAE",
        random_seed=42,
        verbose=False,
        allow_writing_files=False,
        thread_count=2,
    )

    model.fit(
        X_train,
        y_train,
        cat_features=CAT_FEATURES,
        eval_set=(X_val, y_val),
        early_stopping_rounds=50,
        verbose=False,
    )

    pred = model.predict(X_val)

    mae = mean_absolute_error(y_val, pred)
    rmse = np.sqrt(mean_squared_error(y_val, pred))
    r2 = r2_score(y_val, pred)

    results.append({
        **params,
        "Best_Iteration": int(model.get_best_iteration()),
        "MAE": float(mae),
        "RMSE": float(rmse),
        "R2": float(r2),
    })

    print(f"  MAE={mae:.4f}, RMSE={rmse:.4f}, R2={r2:.4f}")

    if mae < best_mae:
        best_mae = mae
        best_model = model
        best_params = params.copy()

results_df = pd.DataFrame(results).sort_values("MAE")
results_df.to_csv(OUTPUT_DIR / "tuning_results.csv", index=False)

best_model_path = MODEL_DIR / "catboost_tuned_yield.cbm"
best_model.save_model(str(best_model_path))

best_info = {
    "model": "CatBoost",
    "target": TARGET,
    "train_years": "2016-2023",
    "validation_year": 2024,
    "test_year_used_for_tuning": False,
    "best_params": best_params,
    "best_iteration": int(best_model.get_best_iteration()),
    "validation_MAE": float(best_mae),
    "validation_RMSE": float(
        np.sqrt(mean_squared_error(y_val, best_model.predict(X_val)))
    ),
    "validation_R2": float(r2_score(y_val, best_model.predict(X_val))),
}

with open(OUTPUT_DIR / "best_tuning_result.json", "w") as f:
    json.dump(best_info, f, indent=4)

print("\n=== TUNING RESULTS (sorted by validation MAE) ===")
print(results_df.to_string(index=False))
print("\nBest parameters:", best_params)
print(f"Best validation MAE: {best_mae:.4f}")
print("Tuned model saved:", best_model_path)
print("Results saved:", OUTPUT_DIR / "tuning_results.csv")
print("\nTuning completed. The 2025 test set was not used.")
