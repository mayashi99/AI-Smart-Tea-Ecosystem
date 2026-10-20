
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.component04 import router as component04_router
from app.components.Component02.plantation_health.api import router as component02_router
from app.components.Component02.harvest_readiness.YOLOv11.api import (
    router as harvest_router,
)
from app.components.Component02.expected_yield_prediction.api import (
    router as expected_yield_router,
)
from app.components.Component02.intelligent_harvest_planning.harvest_forecast import router as harvest_forecast_router


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
    # Vite selects the next available development port (for example 5174)
    # when 5173 is already occupied. Keep CORS limited to local development
    # hosts while allowing that normal fallback behaviour.
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
app.include_router(component04_router)


# ============================================================
# ROOT ENDPOINT
# ============================================================

@app.get("/")
def root():
    return {
        "message": "AI Smart Tea Ecosystem API",
        "status": "running",
    }
