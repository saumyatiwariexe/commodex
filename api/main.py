import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

import os

from .config import settings
from db import analytics_conn, app_conn
from db.queries import (
    get_contracts,
    get_prices,
    get_curve,
    get_calendar,
    get_pairs,
    get_spread,
    get_alerts,
    get_backtest_run,
    get_backtest_trades,
    get_backtest_equity,
)
from api.schemas import APIResponse, APIResponseMeta, APIErrorResponse
from api.jobs import submit_job, get_job_status
import time

DUCKDB_PATH = os.getenv("DUCKDB_PATH", ":memory:")
SQLITE_PATH = os.getenv("SQLITE_PATH", ":memory:")

# Dependency to yield database connections
def get_duck():
    with analytics_conn(DUCKDB_PATH) as con:
        yield con


def get_sqlite():
    with app_conn(SQLITE_PATH) as con:
        yield con


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup code could go here
    yield
    # Teardown code could go here


app = FastAPI(
    title="Commodex API",
    version="0.1.0",
    lifespan=lifespan,
    responses={400: {"model": APIErrorResponse}, 500: {"model": APIErrorResponse}},
)

# CORS configuration: prefer configured origins but keep the local wildcard fallback.
app.add_middleware(
    CORSMiddleware,
    allow_origins=getattr(settings, "ALLOWED_ORIGINS", ["*"]),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
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
        "version": "0.1.0",
        "code_version": "1.0.0",
        "snapshot_hash": "placeholder-hash",
    }

from .routers import data, analytics
app.include_router(data.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
