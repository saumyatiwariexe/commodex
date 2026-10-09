import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

import os

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
    responses={400: {"model": APIErrorResponse}, 500: {"model": APIErrorResponse}}
)

# CORS configuration (from env ideally, but hardcoded to * for dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    return {"version": "0.1.0"}


@app.get("/api/v1/contracts", response_model=APIResponse)
def api_get_contracts(con=Depends(get_duck)):
    data = get_contracts(con)
    return APIResponse(data=data)


@app.get("/api/v1/prices", response_model=APIResponse)
def api_get_prices(
    symbol: str,
    from_date: datetime.date = Query(..., alias="from"),
    to_date: datetime.date = Query(..., alias="to"),
    expiry: datetime.date | None = None,
    con=Depends(get_duck)
):
    data = get_prices(con, symbol, from_date, to_date, expiry)
    return APIResponse(data=data)


@app.get("/api/v1/curve", response_model=APIResponse)
def api_get_curve(
    symbol: str,
    as_of: datetime.date,
    con=Depends(get_duck)
):
    data = get_curve(con, symbol, as_of)
    return APIResponse(data=data)


@app.get("/api/v1/calendar", response_model=APIResponse)
def api_get_calendar(
    from_date: datetime.date | None = Query(None, alias="from"),
    to_date: datetime.date | None = Query(None, alias="to"),
    con=Depends(get_duck)
):
    data = get_calendar(con, from_date, to_date)
    return APIResponse(data=data)


@app.get("/api/v1/coverage", response_model=APIResponse)
def api_get_coverage(con=Depends(get_duck)):
    # Basic coverage query (number of rows per contract)
    query = """
        SELECT symbol, expiry_date, MIN(trade_date) as first_date, MAX(trade_date) as last_date, COUNT(*) as days_covered
        FROM bhav_norm
        GROUP BY symbol, expiry_date
        ORDER BY symbol, expiry_date
    """
    cur = con.cursor()
    cur.execute(query)
    fields = [col[0] for col in cur.description]
    data = [dict(zip(fields, row)) for row in cur.fetchall()]
    return APIResponse(data=data)


@app.get("/api/v1/pairs", response_model=APIResponse)
def api_get_pairs(
    as_of: datetime.date,
    con=Depends(get_duck)
):
    data = get_pairs(con, as_of)
    return APIResponse(data=data)


@app.get("/api/v1/spread", response_model=APIResponse)
def api_get_spread(
    pair: str,
    from_date: datetime.date = Query(..., alias="from"),
    to_date: datetime.date = Query(..., alias="to"),
    con=Depends(get_duck)
):
    if "/" not in pair:
        raise HTTPException(400, detail="Pair must be formatted as LEG_A/LEG_B")
    leg_a, leg_b = pair.split("/", 1)
    data = get_spread(con, leg_a, leg_b, from_date, to_date)
    return APIResponse(data=data)


@app.get("/api/v1/signals", response_model=APIResponse)
def api_get_signals(
    as_of: datetime.date,
    con=Depends(get_duck)
):
    from db.queries import get_pairs_for_signals
    from model.signal import generate_signals, SignalConfig
    import pandas as pd

    # Get data for the lookback window (default 100 days should cover lookback 60)
    df = get_pairs_for_signals(con, as_of, lookback_days=100)
    if df.empty:
        return APIResponse(data={"signals": [], "reason": "no_data"})

    # Run the model logic
    cfg = SignalConfig()
    signals_df = generate_signals(df, cfg)

    # Filter to exactly the requested date
    # Convert as_of to matching type (numpy datetime64 or date)
    date_mask = pd.to_datetime(signals_df["trade_date"]).dt.date == as_of
    today_df = signals_df[date_mask]

    # Active signals only (direction != 0)
    active_signals = today_df[today_df["signal_direction"] != 0]

    if active_signals.empty:
        return APIResponse(data={"signals": [], "reason": "no_signal"})

    # Convert to dict, replace NaNs with None for JSON serialization
    data = active_signals.replace({pd.NA: None}).where(pd.notnull(active_signals), None).to_dict(orient="records")
    return APIResponse(data={"signals": data, "reason": "active"})


@app.get("/api/v1/alerts", response_model=APIResponse)
def api_get_alerts(
    from_date: datetime.date | None = Query(None, alias="from"),
    to_date: datetime.date | None = Query(None, alias="to"),
    con=Depends(get_sqlite)
):
    data = get_alerts(con, from_date, to_date)
    return APIResponse(data=data)


@app.get("/api/v1/backtests/{run_id}", response_model=APIResponse)
def api_get_backtest_run(run_id: str, con=Depends(get_duck)):
    data = get_backtest_run(con, run_id)
    if not data:
        raise HTTPException(404, detail="Run not found")
    return APIResponse(data=data)


@app.get("/api/v1/backtests/{run_id}/trades", response_model=APIResponse)
def api_get_backtest_trades(run_id: str, con=Depends(get_duck)):
    data = get_backtest_trades(con, run_id)
    return APIResponse(data=data)


@app.get("/api/v1/backtests/{run_id}/equity", response_model=APIResponse)
def api_get_backtest_equity(run_id: str, con=Depends(get_duck)):
    data = get_backtest_equity(con, run_id)
    return APIResponse(data=data)


# ── Jobs ──────────────────────────────────────────────────────────────────────

# Dummy functions representing the heavy lifting
def actual_ingest_job(from_date: str, to_date: str, log_progress=None):
    from pipeline.ingest import run_ingestion
    from pipeline.adapters import LocalFilesSource
    import datetime
    
    if log_progress: log_progress(f"Starting ingestion from {from_date} to {to_date}")
    
    start_d = datetime.date.fromisoformat(from_date)
    end_d = datetime.date.fromisoformat(to_date)
    
    # Simple loop over days
    current = start_d
    source = LocalFilesSource("data/inbox")
    
    while current <= end_d:
        if current.weekday() < 5:  # Skip weekends as simple heuristic
            if log_progress: log_progress(f"Processing {current}")
            run_ingestion(source, current, "data", DUCKDB_PATH)
        current += datetime.timedelta(days=1)
        
    if log_progress: log_progress("Ingestion complete")

def dummy_backtest_job(config: dict, log_progress=None):
    if log_progress: log_progress("Initializing backtest engine")
    time.sleep(2)
    if log_progress: log_progress("Running walk-forward folds")
    time.sleep(3)
    if log_progress: log_progress("Calculating performance attribution")
    time.sleep(1)
    if log_progress: log_progress("Saving backtest results")


@app.post("/api/v1/ingest", response_model=APIResponse)
def api_post_ingest(
    from_date: datetime.date = Query(..., alias="from"),
    to_date: datetime.date = Query(..., alias="to")
):
    job_id = submit_job(SQLITE_PATH, "ingest", actual_ingest_job, str(from_date), str(to_date))
    return APIResponse(data={"job_id": job_id, "status": "pending"})


@app.post("/api/v1/backtests", response_model=APIResponse)
def api_post_backtest(config: dict):
    job_id = submit_job(SQLITE_PATH, "backtest", dummy_backtest_job, config)
    return APIResponse(data={"job_id": job_id, "status": "pending"})


@app.get("/api/v1/jobs/{job_id}", response_model=APIResponse)
def api_get_job(job_id: str):
    data = get_job_status(SQLITE_PATH, job_id)
    if not data:
        raise HTTPException(404, detail="Job not found")
    return APIResponse(data=data)
