
from fastapi import APIRouter, FastAPI, File, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool
from ...image_validation import validate_tea_image, MAX_IMAGE_BYTES
from DL.models.component02.harvest_readiness.yolo11.inference import DEVICE, get_model

app = FastAPI(title="Tea Harvest Readiness API")
router = APIRouter(tags=["Harvest Readiness"])

device = DEVICE


@app.get("/")
def home():
    return {"message": "Tea Harvest Readiness API is running"}


@router.post("/predict")
async def predict(file: UploadFile = File(...)):
    allowed_types = {"image/jpeg", "image/png", "image/webp"}

    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Upload a JPG, PNG, or WEBP image."
        )

    image_bytes = await file.read(MAX_IMAGE_BYTES + 1)

    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded image is empty.")

    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Maximum image size is 10 MB.")

    await run_in_threadpool(validate_tea_image, image_bytes, file.filename or "image")

    import io
    from PIL import Image, UnidentifiedImageError

    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except (UnidentifiedImageError, OSError, ImportError):
        raise HTTPException(status_code=400, detail="Invalid image file.")

    try:
        model = get_model()
        results = model.predict(
            source=image,
            imgsz=224,
            device=device,
            verbose=False
        )

        result = results[0]

        if result.probs is None:
            raise HTTPException(
                status_code=500,
                detail="Model did not return classification probabilities."
            )

        class_id = int(result.probs.top1)
        class_name = model.names[class_id]
        confidence = float(result.probs.top1conf)

        return {
            "filename": file.filename,
            "prediction": class_name,
            "confidence": round(confidence, 4),
            "confidence_percent": round(confidence * 100, 2)
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Prediction failed: {str(exc)}"
        ) from exc


# Retain the standalone API for command-line clients; the frontend uses app.main.
app.include_router(router)
