from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.components.component04.api import router as component04_router
from app.components.component3.api import (
    router as component3_router,
    tea_grade_router,
)
from app.config import CORS_ORIGINS

app = FastAPI(
    title="AI Smart Tea Ecosystem API",
    description="Backend API powering the AI Smart Tea Ecosystem for the Sri Lankan Tea Industry, including YOLO11 Tea Grade Classification and Purity Analysis.",
    version="1.0.0",
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Component 03 (Tea Grade, Purity, Mixed Composition & Defect Analysis) routers
app.include_router(component3_router)
app.include_router(tea_grade_router)

# Mount Component 04 (Export Intelligence & Price/Demand Forecasting) router
app.include_router(component04_router)


@app.get("/")
def root():
    return {
        "project": "AI-Smart-Tea-Ecosystem",
        "description": "Smart Tea Ecosystem for Sri Lankan Tea Industry",
        "status": "online",
        "endpoints": {
            "docs": "/docs",
            "redoc": "/redoc",
            "component03": {
                "name": "Tea Grade Classification, Purity, Mixed Composition & Defect Analysis",
                "predict": "/api/component3/predict",
                "purity": "/api/component3/purity",
                "info": "/api/component3/info",
                "health": "/api/component3/health",
                "grades": "/api/component3/grades",
                "tea_grade_predict": "/api/tea-grade/predict",
                "tea_grade_purity": "/api/tea-grade/purity",
                "tea_grade_info": "/api/tea-grade/info",
                "tea_grade_health": "/api/tea-grade/health",
                "tea_grade_grades": "/api/tea-grade/grades",
            },
            "component04": {
                "name": "Export Intelligence & Price/Demand Forecasting",
                "health": "/api/component04/health",
                "info": "/api/component04/info",
            },
        },
    }