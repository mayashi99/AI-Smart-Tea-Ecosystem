"""
Component 03: AI-Powered Tea Grade, Purity, Mixed Composition & Defect Analysis
"""

from app.components.component3.predict import (
    predict_tea_grade,
    get_model_info,
    resolve_model_path,
    get_loaded_model,
)
from app.components.component3.purity import (
    analyze_tea_purity,
)
from app.components.component3.api import (
    router,
    tea_grade_router,
)
from app.components.component3.train import (
    train_tea_grade_model,
)
from app.components.component3.evaluate import (
    evaluate_tea_model,
)
from app.components.component3.validator import (
    validate_tea_sample_image,
)

__all__ = [
    "predict_tea_grade",
    "get_model_info",
    "resolve_model_path",
    "get_loaded_model",
    "analyze_tea_purity",
    "train_tea_grade_model",
    "evaluate_tea_model",
    "validate_tea_sample_image",
    "router",
    "tea_grade_router",
]
