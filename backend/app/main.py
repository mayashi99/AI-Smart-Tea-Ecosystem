from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.component04 import router as component04_router

app = FastAPI()

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
    return {"message": "AI Smart Tea Ecosystem API"}
