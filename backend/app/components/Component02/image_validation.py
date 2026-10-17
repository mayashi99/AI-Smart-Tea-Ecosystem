"""Local, zero-shot image screening; not a calibrated tea-species classifier.

Keep this separate from the healthy/low-health classifier: its confidence
cannot tell us whether an uploaded photograph belongs to either class.
"""
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from threading import Lock

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError

MODEL_ID = "openai/clip-vit-base-patch32"
MODEL_DIR = Path(__file__).resolve().parent / "models" / "tea_image_screening"
MAX_IMAGE_BYTES = 10 * 1024 * 1024
TEA_PROMPTS = (
    "a photograph of tea leaves on a tea plant",
    "a photograph of a tea plantation with tea bushes",
    "a close-up photograph of diseased or damaged tea leaves",
    "a photograph of freshly picked green tea leaves",
)
OTHER_PROMPTS = (
    "a photograph of a person or a selfie",
    "a screenshot of a website, document, chart or computer screen",
    "a photograph of a car, motorcycle or other vehicle",
    "a photograph of a building, street or room",
    "a photograph of an animal, bird or insect",
    "a photograph of food or a cup of tea",
    "a photograph of a phone, computer or household object",
    "a drawing, logo, cartoon or text",
    "a photograph of flowers, fruit or vegetables",
    "a photograph of a lawn or a forest landscape",
    "a photograph of maple leaves, palm fronds or pine needles",
    "a blank, blurry or unrecognizable image",
)
_model_lock = Lock()


@lru_cache(maxsize=1)
def _load_model():
    # Provision explicitly; never download weights during an upload request.
    from transformers import CLIPModel, CLIPProcessor
    processor = CLIPProcessor.from_pretrained(MODEL_DIR, local_files_only=True, use_fast=False)
    model = CLIPModel.from_pretrained(MODEL_DIR, local_files_only=True).eval()
    return processor, model


def _is_tea_image(image):
    import torch
    with _model_lock:
        processor, model = _load_model()
        inputs = processor(text=list(TEA_PROMPTS + OTHER_PROMPTS), images=image,
                           return_tensors="pt", padding=True)
        with torch.inference_mode():
            scores = model(**inputs).logits_per_image[0]
        tea_score = scores[:len(TEA_PROMPTS)].max().item()
        other_score = scores[len(TEA_PROMPTS):].max().item()
    # Similarity margin, not a probability or measured accuracy. Reject ties
    # and ambiguous inputs rather than showing an unsupported health result.
    return tea_score >= other_score + 2.0


def validate_tea_image(image_bytes, filename):
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(413, f"'{filename}' is too large. Maximum image size is 10 MB.")
    try:
        with Image.open(BytesIO(image_bytes), formats=["JPEG", "PNG", "WEBP"]) as source:
            if source.width * source.height > 25_000_000:
                raise HTTPException(400, f"'{filename}' is too large. Use an image under 25 megapixels.")
            source.load()
            image = ImageOps.exif_transpose(source).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError, ImportError, Image.DecompressionBombError) as exc:
        raise HTTPException(400, f"Cannot read '{filename}'. Please upload a valid JPG, PNG or WEBP photo.") from exc
    try:
        accepted = _is_tea_image(image)
    except Exception as exc:
        raise HTTPException(503, "Image validation is temporarily unavailable. Please try again later.") from exc
    finally:
        image.close()
    if not accepted:
        raise HTTPException(422, f"Could not identify tea leaves or a tea plantation in '{filename}'. Please upload a clear photo of tea leaves or tea plants.")
