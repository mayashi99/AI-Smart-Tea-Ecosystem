
from pathlib import Path

import torch
from fastapi import FastAPI, File, HTTPException, UploadFile
from ultralytics import YOLO

app = FastAPI(title="Tea Harvest Readiness API")

BASE_DIR = Path(__file__).resolve().parent

MODEL_PATH = (
    BASE_DIR
    / "runs"
    / "harvest_readiness_yolo11n_50epochs"
    / "weights"
    / "best.pt"
)

if not MODEL_PATH.is_file():
    raise FileNotFoundError(f"Model not found: {MODEL_PATH}")

device = "mps" if torch.backends.mps.is_available() else "cpu"
model = YOLO(str(MODEL_PATH))


@app.get("/")
def home():
    return {"message": "Tea Harvest Readiness API is running"}


@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    allowed_types = {"image/jpeg", "image/png", "image/webp"}

    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Upload a JPG, PNG, or WEBP image."
        )

    image_bytes = await file.read()

    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded image is empty.")

    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Maximum image size is 10 MB.")

    import io
    from PIL import Image, UnidentifiedImageError

    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except (UnidentifiedImageError, OSError):
        raise HTTPException(status_code=400, detail="Invalid image file.")

    try:
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
