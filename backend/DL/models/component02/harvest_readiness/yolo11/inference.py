"""Lazy YOLO11 loader for harvest-readiness API inference."""

from functools import lru_cache

import torch
from fastapi import HTTPException
from ultralytics import YOLO

from DL.utils.component02.paths import HARVEST_YOLO_MODEL


DEVICE = "mps" if torch.backends.mps.is_available() else "cpu"


@lru_cache(maxsize=1)
def get_model():
    """Load the production model once, without blocking API startup if absent."""
    if not HARVEST_YOLO_MODEL.is_file():
        raise HTTPException(status_code=503, detail="Harvest readiness model is unavailable.")
    return YOLO(str(HARVEST_YOLO_MODEL))
