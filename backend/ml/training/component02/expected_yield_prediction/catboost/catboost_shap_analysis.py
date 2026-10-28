
import pandas as pd
import shap
import matplotlib.pyplot as plt
from catboost import CatBoostRegressor

from ml.utils.component02.expected_yield_prediction.paths import (
    PROCESSED_DATA_DIR,
    evaluation_dir,
    model_dir,
)

DATA_PATH = PROCESSED_DATA_DIR / "validation.csv"
MODEL_PATH = model_dir("catboost") / "catboost_yield.cbm"
OUTPUT_DIR = evaluation_dir("catboost")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FEATURES = [
    "Year",
    "Month_Number",
    "Week_Number",
    "Temperature",
    "Rainfall_mm",
    "Humidity",
    "Wind_Speed",
    "Solar_Radiation",
    "Location",
    "Grown_Type",
]

# Load validation data (2024); do not use 2025 test data.
df = pd.read_csv(DATA_PATH)

missing = set(FEATURES) - set(df.columns)
if missing:
    raise ValueError(f"Missing columns: {sorted(missing)}")

X = df[FEATURES].copy()

# Sample up to 200 rows to reduce memory and runtime.
X_sample = X.sample(
    n=min(200, len(X)),
    random_state=42
)

model = CatBoostRegressor()
model.load_model(str(MODEL_PATH))

print("Calculating SHAP values...")
explainer = shap.TreeExplainer(model)
shap_values = explainer(X_sample)

# Save mean absolute SHAP importance.
importance = pd.DataFrame({
    "Feature": FEATURES,
    "Mean_Absolute_SHAP": abs(shap_values.values).mean(axis=0),
}).sort_values(
    "Mean_Absolute_SHAP",
    ascending=False
)

importance_path = OUTPUT_DIR / "shap_importance.csv"
importance.to_csv(importance_path, index=False)

# Save global summary plot.
shap.summary_plot(
    shap_values,
    X_sample,
    show=False
)

plt.tight_layout()
plot_path = OUTPUT_DIR / "shap_summary.png"
plt.savefig(plot_path, dpi=200, bbox_inches="tight")
plt.close()

print("\n=== SHAP FEATURE IMPORTANCE ===")
print(importance.to_string(index=False))
print(f"\nSaved: {importance_path}")
print(f"Saved: {plot_path}")

