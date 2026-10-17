from app.api.component04 import router as component04_router

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.components.Component02.api import router as component02_router
from app.components.Component02.harvest_readiness.api import (
    router as harvest_router,
)
from app.components.Component02.expected_yield_prediction.api import (
    router as expected_yield_router,
)
from app.components.Component02.harvest_forecast import router as harvest_forecast_router


# ============================================================
# MAIN FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="AI Smart Tea Ecosystem API",
    version="1.0.0",
)


# ============================================================
# CORS CONFIGURATION
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


# ============================================================
# COMPONENT 02 - EXISTING PLANTATION HEALTH API
# ============================================================

app.include_router(component02_router)


# ============================================================
# COMPONENT 02 - EXISTING HARVEST READINESS API
# ============================================================

app.include_router(
    harvest_router,
    prefix="/component02/harvest-readiness",
)


# ============================================================
# COMPONENT 02 - EXPECTED YIELD PREDICTION API
# ============================================================

app.include_router(expected_yield_router)
app.include_router(harvest_forecast_router)


# ============================================================
# ROOT ENDPOINT
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(component04_router)


@app.get("/")
def root():
    return {
        "message": "AI Smart Tea Ecosystem API",
        "status": "running",
    }
