import io
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from PIL import Image

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

from app.config import (
    CANDIDATE_MODEL_PATHS,
    DEFAULT_MODEL_PATH,
    TEA_GRADES_INFO,
    ALLOWED_EXTENSIONS,
)
from app.components.component3.validator import validate_tea_sample_image

logger = logging.getLogger(__name__)

# Global model cache for Component 03
_cached_model = None
_cached_model_path: Optional[Path] = None


def resolve_model_path() -> Optional[Path]:
    """
    Finds the first existing YOLO11 classification model weights file among candidate paths.
    """
    for candidate in CANDIDATE_MODEL_PATHS:
        try:
            if candidate and candidate.is_file():
                return candidate
        except Exception:
            continue
    return None


def get_loaded_model():
    """
    Retrieves the cached YOLO model or loads it if not already initialized.
    """
    global _cached_model, _cached_model_path

    if _cached_model is not None:
        return _cached_model, _cached_model_path

    if YOLO is None:
        raise RuntimeError(
            "The 'ultralytics' package is not installed. "
            "Please run 'pip install ultralytics' to enable YOLO11 classification inference."
        )

    resolved_path = resolve_model_path()
    if resolved_path is None:
        searched_paths = "\n - ".join(str(p) for p in CANDIDATE_MODEL_PATHS)
        raise FileNotFoundError(
            f"Trained YOLO11 classification model weights not found. Searched candidate paths:\n - {searched_paths}\n"
            "Please set the TEA_MODEL_PATH environment variable or ensure the model file is available at "
            f"'{DEFAULT_MODEL_PATH}'."
        )

    logger.info(f"[Component 03] Loading YOLO11 classification model from: {resolved_path}")
    model = YOLO(str(resolved_path))
    _cached_model = model
    _cached_model_path = resolved_path
    return _cached_model, _cached_model_path


def get_model_info() -> Dict[str, Any]:
    """
    Returns diagnostic details about the YOLO11 model configured for Component 03.
    """
    resolved_path = resolve_model_path()
    is_available = resolved_path is not None and resolved_path.is_file()

    classes_list = []
    if is_available:
        try:
            model, _ = get_loaded_model()
            if hasattr(model, "names") and isinstance(model.names, dict):
                classes_list = [model.names[i] for i in sorted(model.names.keys())]
        except Exception as e:
            logger.warning(f"[Component 03] Could not inspect model names: {e}")

    if not classes_list:
        classes_list = list(TEA_GRADES_INFO.keys())

    return {
        "component": "Component 03: AI-Powered Tea Grade, Purity, Mixed Composition & Defect Analysis",
        "model_available": is_available,
        "resolved_model_path": str(resolved_path) if resolved_path else None,
        "default_expected_path": str(DEFAULT_MODEL_PATH),
        "model_architecture": "YOLO11 Classification (Whole-Image)",
        "bounding_box_support": False,
        "explainable_ai_support": False,
        "supported_classes": classes_list,
        "feature_status": {
            "tea_grade_classification": "active",
            "purity_analysis": "not_implemented",
            "mixed_composition_analysis": "not_implemented",
            "defect_analysis": "not_implemented",
            "overall_quality_index": "not_implemented",
        },
        "notice": "Whole-image classification model. Particle bounding boxes, heatmaps, and Grad-CAM++ are not generated.",
    }


def predict_tea_grade(image_bytes: bytes, filename: Optional[str] = None) -> Dict[str, Any]:
    """
    Runs YOLO11 classification inference on uploaded tea leaf image bytes for Component 03.
    Returns:
        Dict with predicted grade, confidence score, top-5 ranked classes, and explicit status
        for unimplemented research sub-features (purity, mixed composition, defect analysis).
    """
    # 1. Validate image format
    if filename:
        ext = Path(filename).suffix.lower()
        if ext and ext not in ALLOWED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file extension '{ext}'. Allowed formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )

    try:
        pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as e:
        raise ValueError(f"Invalid or corrupted image file: {str(e)}")

    # 2. Pre-inference sample validation (visual / color / skin tone / dark particles check)
    is_valid, validation_error = validate_tea_sample_image(pil_image)
    if not is_valid:
        raise ValueError(validation_error)

    # 3. Get loaded YOLO model
    model, model_path = get_loaded_model()

    # 4. Perform classification prediction
    # Classification inference uses standard imgsz=224
    results = model.predict(source=pil_image, imgsz=224, verbose=False)
    if not results or len(results) == 0:
        raise RuntimeError("YOLO model returned no predictions for the provided image.")

    r = results[0]
    probs = getattr(r, "probs", None)
    if probs is None:
        raise RuntimeError(
            "No classification probabilities returned by YOLO. Ensure the model is a YOLO classification model (*-cls)."
        )

    # 5. Post-inference OOD confidence & ambiguity check
    is_valid_ood, ood_error = validate_tea_sample_image(pil_image, probs=probs)
    if not is_valid_ood:
        raise ValueError(ood_error)

    # 4. Extract top-1 prediction
    top1_index = int(probs.top1)
    predicted_grade = model.names[top1_index]
    top1_conf = float(probs.top1conf)

    # 5. Extract top-5 predictions
    top5_list: List[Dict[str, Any]] = []
    num_classes = len(model.names)

    if hasattr(probs, "top5") and probs.top5 is not None:
        for idx, conf in zip(probs.top5, probs.top5conf):
            idx_int = int(idx)
            grade_name = model.names[idx_int]
            conf_float = float(conf)
            grade_meta = TEA_GRADES_INFO.get(grade_name, {})
            top5_list.append({
                "rank": len(top5_list) + 1,
                "grade": grade_name,
                "full_name": grade_meta.get("name", grade_name),
                "category": grade_meta.get("category", "Tea Grade"),
                "confidence": round(conf_float, 4),
                "confidence_percentage": round(conf_float * 100, 2),
            })
    else:
        # Fallback ranking if top5 attribute is unavailable
        all_confs = probs.data.tolist()
        sorted_indices = sorted(
            range(len(all_confs)), key=lambda i: all_confs[i], reverse=True
        )[:min(5, num_classes)]

        for rank, idx in enumerate(sorted_indices, start=1):
            grade_name = model.names[idx]
            conf_float = float(all_confs[idx])
            grade_meta = TEA_GRADES_INFO.get(grade_name, {})
            top5_list.append({
                "rank": rank,
                "grade": grade_name,
                "full_name": grade_meta.get("name", grade_name),
                "category": grade_meta.get("category", "Tea Grade"),
                "confidence": round(conf_float, 4),
                "confidence_percentage": round(conf_float * 100, 2),
            })

    # 6. Build all probabilities map
    all_probabilities: Dict[str, float] = {}
    if hasattr(probs, "data"):
        raw_confs = probs.data.tolist()
        for i, conf_val in enumerate(raw_confs):
            if i in model.names:
                all_probabilities[model.names[i]] = round(float(conf_val), 4)

    # 7. Metadata for top-1 grade
    top_meta = TEA_GRADES_INFO.get(predicted_grade, {})

    return {
        "success": True,
        "component": "Component 03: AI-Powered Tea Grade, Purity, Mixed Composition & Defect Analysis",
        "predicted_grade": predicted_grade,
        "grade_full_name": top_meta.get("name", predicted_grade),
        "grade_category": top_meta.get("category", "Standard Sri Lankan Tea Grade"),
        "grade_description": top_meta.get("description", ""),
        "confidence": round(top1_conf, 4),
        "confidence_percentage": round(top1_conf * 100, 2),
        "top5": top5_list,
        "all_probabilities": all_probabilities,
        # Explicit status for unimplemented Component 03 analytical capabilities
        "unimplemented_features": {
            "purity_analysis": {
                "implemented": True,
                "status": "Experimental Baseline (Computer Vision)",
                "message": "Experimental color uniformity & anomaly detection is active via /api/component3/purity. Note: Validated commercial purity percentages require ground-truth laboratory purity labels.",
                "endpoint": "/api/component3/purity",
            },
            "mixed_composition_analysis": {
                "implemented": False,
                "status": "Not Implemented",
                "message": "Mixed composition analysis requires multi-label segmentation and is not yet implemented.",
            },
            "defect_analysis": {
                "implemented": False,
                "status": "Not Implemented",
                "message": "Leaf defect identification model is not yet implemented.",
            },
            "overall_quality_score": {
                "implemented": False,
                "status": "Not Implemented",
                "message": "Comprehensive quality index model is not yet implemented.",
            },
        },
        "model_info": {
            "model_path": str(model_path),
            "architecture": "YOLO11 Classification (Whole-Image)",
            "bounding_boxes": False,
            "explainable_ai": False,
            "description": "Evaluates whole-image leaf texture and particle morphology. No particle bounding boxes, heatmaps, or Grad-CAM++ are generated.",
        },
    }
