import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from fastapi.responses import JSONResponse

from app.components.component3.predict import (
    predict_tea_grade,
    get_model_info,
)
from app.components.component3.purity import (
    analyze_tea_purity,
)
from app.config import (
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE_MB,
    TEA_GRADES_INFO,
)

logger = logging.getLogger(__name__)

# Primary router for Component 03
router = APIRouter(
    prefix="/api/component3",
    tags=["Component 03: Tea Grade, Purity, Mixed Composition & Defect Analysis"],
)

# Alias / standard router for tea-grade endpoints (all belonging to Component 03)
tea_grade_router = APIRouter(
    prefix="/api/tea-grade",
    tags=["Component 03: Tea Grade Classification (Standard/Legacy Route)"],
)


# Shared endpoint implementations
def get_component3_health():
    """
    Health check endpoint for Component 03.
    """
    return {
        "status": "online",
        "component": "Component 03: AI-Powered Tea Grade, Purity, Mixed Composition & Defect Analysis",
        "service": "Tea Grade Classification & Purity Analysis",
        "model_framework": "Ultralytics YOLO11",
        "active_modules": [
            "tea_grade_classification",
            "purity_analysis_experimental",
        ],
        "pending_modules": [
            "purity_ground_truth_model",
            "mixed_composition",
            "defect_analysis",
            "quality_score",
        ],
    }


def get_component3_info():
    """
    Retrieves model status, file location, loaded classes, and architecture information for Component 03.
    """
    info = get_model_info()
    if "feature_status" in info and isinstance(info["feature_status"], dict):
        info["feature_status"]["purity_analysis"] = "experimental_baseline"
    return info


def get_component3_grades():
    """
    Returns the supported Sri Lankan tea grades along with their commercial descriptions.
    """
    return {
        "count": len(TEA_GRADES_INFO),
        "grades": TEA_GRADES_INFO,
    }


async def execute_predict_grade(file: UploadFile):
    """
    Accepts an uploaded tea leaf sample image and runs YOLO11 classification inference.
    Returns the predicted grade, confidence score, and top-5 ranked classes.
    """
    if not file or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No image file was provided.",
        )

    # 1. Validate file extension
    filename = file.filename.lower()
    ext_matched = any(filename.endswith(ext) for ext in ALLOWED_EXTENSIONS)
    if not ext_matched:
        allowed_str = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type '{file.filename}'. Supported formats are: {allowed_str}.",
        )

    # 2. Read image content with size limitation
    try:
        contents = await file.read()
    except Exception as e:
        logger.error(f"[Component 03] Failed to read uploaded file: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not read uploaded image data: {str(e)}",
        )

    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image file size ({len(contents) / (1024*1024):.1f} MB) exceeds maximum allowed limit of {MAX_FILE_SIZE_MB} MB.",
        )

    if len(contents) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded image file is empty.",
        )

    # 3. Execute classification prediction
    try:
        prediction_result = predict_tea_grade(contents, filename=file.filename)
        return JSONResponse(status_code=status.HTTP_200_OK, content=prediction_result)
    except FileNotFoundError as e:
        logger.error(f"[Component 03] Model file error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Classification model unavailable: {str(e)}",
        )
    except ValueError as e:
        logger.warning(f"[Component 03] Invalid image format: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except RuntimeError as e:
        logger.error(f"[Component 03] Prediction runtime error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference error: {str(e)}",
        )
    except Exception as e:
        logger.exception(f"[Component 03] Unexpected error during tea grade prediction: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during prediction: {str(e)}",
        )


async def execute_analyze_purity(file: UploadFile):
    """
    Accepts an uploaded dry-tea sample image and runs experimental computer-vision
    homogeneity and anomaly analysis.
    Explicitly refuses to fabricate unvalidated commercial purity percentages.
    """
    if not file or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No image file was provided.",
        )

    # 1. Validate file extension
    filename = file.filename.lower()
    ext_matched = any(filename.endswith(ext) for ext in ALLOWED_EXTENSIONS)
    if not ext_matched:
        allowed_str = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type '{file.filename}'. Supported formats are: {allowed_str}.",
        )

    # 2. Read image content with size limitation
    try:
        contents = await file.read()
    except Exception as e:
        logger.error(f"[Component 03] Failed to read uploaded file for purity: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not read uploaded image data: {str(e)}",
        )

    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image file size ({len(contents) / (1024*1024):.1f} MB) exceeds maximum allowed limit of {MAX_FILE_SIZE_MB} MB.",
        )

    if len(contents) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded image file is empty.",
        )

    # 3. Execute purity analysis
    try:
        purity_result = analyze_tea_purity(contents, filename=file.filename)
        return JSONResponse(status_code=status.HTTP_200_OK, content=purity_result)
    except ValueError as e:
        logger.warning(f"[Component 03] Invalid image format for purity: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"[Component 03] Unexpected error during purity analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during purity analysis: {str(e)}",
        )


# Register endpoints on primary router (/api/component3)
@router.get("/health")
def health_endpoint():
    return get_component3_health()

@router.get("/info")
def info_endpoint():
    return get_component3_info()

@router.get("/grades")
def grades_endpoint():
    return get_component3_grades()

@router.post("/predict")
async def predict_endpoint(file: UploadFile = File(...)):
    return await execute_predict_grade(file)

@router.post("/purity")
async def purity_endpoint(file: UploadFile = File(...)):
    return await execute_analyze_purity(file)


# Register endpoints on legacy/standard router (/api/tea-grade)
@tea_grade_router.get("/health")
def tea_grade_health():
    return get_component3_health()

@tea_grade_router.get("/info")
def tea_grade_info():
    return get_component3_info()

@tea_grade_router.get("/grades")
def tea_grade_grades():
    return get_component3_grades()

@tea_grade_router.post("/predict")
async def tea_grade_predict(file: UploadFile = File(...)):
    return await execute_predict_grade(file)

@tea_grade_router.post("/purity")
async def tea_grade_purity(file: UploadFile = File(...)):
    return await execute_analyze_purity(file)
