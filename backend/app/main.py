from fastapi import FastAPI

from app.components.Component02.api import router as component02_router


# ============================================================
# MAIN FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="AI Smart Tea Ecosystem API",
    version="1.0.0"
)


# ============================================================
# COMPONENT 02 - PLANTATION HEALTH
# ============================================================

app.include_router(component02_router)


# ============================================================
# ROOT ENDPOINT
# ============================================================

@app.get("/")
def root():
    return {
        "message": "AI Smart Tea Ecosystem API",
        "status": "running"
    }