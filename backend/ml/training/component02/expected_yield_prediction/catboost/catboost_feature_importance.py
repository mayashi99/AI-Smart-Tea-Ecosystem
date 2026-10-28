
import pandas as pd
from catboost import CatBoostRegressor

from ml.utils.component02.expected_yield_prediction.paths import evaluation_dir, model_dir

MODEL_PATH = model_dir("catboost") / "catboost_yield.cbm"
OUTPUT_DIR = evaluation_dir("catboost")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

if not MODEL_PATH.exists():
    raise FileNotFoundError(f"Model not found: {MODEL_PATH}")

model = CatBoostRegressor()
model.load_model(str(MODEL_PATH))

feature_names = model.feature_names_
importance_values = model.get_feature_importance()

importance_df = pd.DataFrame({
    "Feature": feature_names,
    "Importance": importance_values,
})

importance_df = importance_df.sort_values(
    "Importance", ascending=False
).reset_index(drop=True)

output_path = OUTPUT_DIR / "feature_importance.csv"
importance_df.to_csv(output_path, index=False)

print("=" * 50)
print("CATBOOST FEATURE IMPORTANCE")
print("=" * 50)
print(importance_df.to_string(index=False))
print(f"\nSaved: {output_path}")

