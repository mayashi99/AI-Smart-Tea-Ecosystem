
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.components.Component02.expected_yield_prediction.catboost.predict import (
    predict_yield,
)

router = APIRouter(
    prefix="/component02/expected-yield",
    tags=["Expected Yield Prediction"],
)


class YieldPredictionRequest(BaseModel):
    Year: int = Field(ge=2016, le=2100)
    Month_Number: int = Field(ge=1, le=12)
    Week_Number: int = Field(ge=1, le=4)

    Temperature: float
    Rainfall_mm: float = Field(ge=0)
    Humidity: float = Field(ge=0, le=100)
    Wind_Speed: float = Field(ge=0)
    Solar_Radiation: float = Field(ge=0)

    Location: str
    Grown_Type: str


@router.get("/health")
def expected_yield_health():
    return {
        "component": "Expected Yield Prediction",
        "status": "available",
    }


@router.post("/predict")
def predict_expected_yield(request: YieldPredictionRequest):
    try:
        prediction = predict_yield(request.model_dump())

        return {
            "location": request.Location,
            "year": request.Year,
            "month": request.Month_Number,
            "week": request.Week_Number,
            "predicted_kg_per_Acre": prediction,
            "unit": "kg/acre",
            "model": "CatBoost",
        }

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=500,
            detail="Expected yield model file was not found.",
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
