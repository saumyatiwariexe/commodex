from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings

app = FastAPI(title="Commodex API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.get("/readyz")
def readyz():
    return {"status": "ready"}

@app.get("/version")
def version():
    return {
        "code_version": "1.0.0",
        "snapshot_hash": "placeholder-hash"
    }

from .routers import data, analytics
app.include_router(data.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
