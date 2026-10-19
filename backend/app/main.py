from fastapi import FastAPI
<<<<<<< HEAD

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Hello World"}
=======
from fastapi.middleware.cors import CORSMiddleware
import os

from app.api.component04 import router as component04_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(component04_router)


@app.get("/")
def root():
    return {"message": "AI Smart Tea Ecosystem API"}
>>>>>>> 119d635afe96b6dd3265084713f2cdfb831272f2
