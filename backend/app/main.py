from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.components.Component02.api import router as component02_router
from app.components.Component02.harvest_readiness.api import router as harvest_router


# ============================================================
# MAIN FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="AI Smart Tea Ecosystem API",
    version="1.0.0"
)

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
# COMPONENT 02 - PLANTATION HEALTH
# ============================================================

app.include_router(component02_router)
app.include_router(harvest_router, prefix="/component02/harvest-readiness")


# ============================================================
# ROOT ENDPOINT
# ============================================================

@app.get("/")
def root():
    return {
        "message": "AI Smart Tea Ecosystem API",
        "status": "running"
    }
