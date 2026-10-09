"""
api/jobs.py
===========
Simple in-process job runner for backtests and ingestion.
Persists status to SQLite.
"""

import datetime
import logging
import uuid
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Any

from db import app_conn

logger = logging.getLogger(__name__)

# Single thread pool for all background tasks
# BACKEND.md spec: "One backtest at a time per user to avoid CPU contention."
# Since we only have a simple runner, a thread pool of size 2 is reasonable (1 ingest, 1 backtest).
_executor = ThreadPoolExecutor(max_workers=2)

def submit_job(sqlite_path: str, job_type: str, func: Callable, *args, **kwargs) -> str:
    """Submit a background job and record it in SQLite."""
    job_id = f"job-{uuid.uuid4().hex[:8]}"
    now = datetime.datetime.now(datetime.UTC).isoformat()
    
    with app_conn(sqlite_path) as con:
        con.execute(
            """
            INSERT INTO background_jobs (job_id, job_type, status, progress, error, created_at, updated_at)
            VALUES (?, ?, 'pending', '[]', NULL, ?, ?)
            """,
            (job_id, job_type, now, now)
        )
    
    # Fire and forget
    _executor.submit(_run_job, sqlite_path, job_id, func, *args, **kwargs)
    return job_id


def _run_job(sqlite_path: str, job_id: str, func: Callable, *args, **kwargs):
    """Wrapper that executes the job function and updates status."""
    now = datetime.datetime.now(datetime.UTC).isoformat()
    with app_conn(sqlite_path) as con:
        con.execute(
            "UPDATE background_jobs SET status = 'running', updated_at = ? WHERE job_id = ?",
            (now, job_id)
        )
    
    def log_progress(msg: str):
        """Callback to log progress per step."""
        with app_conn(sqlite_path) as con:
            row = con.execute("SELECT progress FROM background_jobs WHERE job_id = ?", (job_id,)).fetchone()
            if row and row["progress"]:
                try:
                    prog_list = json.loads(row["progress"])
                except json.JSONDecodeError:
                    prog_list = []
            else:
                prog_list = []
            
            prog_list.append({"time": datetime.datetime.now(datetime.UTC).isoformat(), "msg": msg})
            
            con.execute(
                "UPDATE background_jobs SET progress = ?, updated_at = ? WHERE job_id = ?",
                (json.dumps(prog_list), datetime.datetime.now(datetime.UTC).isoformat(), job_id)
            )

    try:
        # Pass log_progress if the func supports it via kwargs
        kwargs["log_progress"] = log_progress
        func(*args, **kwargs)
        status = "completed"
        error = None
    except Exception as e:
        logger.exception("Job %s failed", job_id)
        status = "failed"
        error = str(e)

    now = datetime.datetime.now(datetime.UTC).isoformat()
    with app_conn(sqlite_path) as con:
        con.execute(
            "UPDATE background_jobs SET status = ?, error = ?, updated_at = ? WHERE job_id = ?",
            (status, error, now, job_id)
        )


def get_job_status(sqlite_path: str, job_id: str) -> dict[str, Any] | None:
    with app_conn(sqlite_path) as con:
        row = con.execute("SELECT * FROM background_jobs WHERE job_id = ?", (job_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        if d.get("progress"):
            try:
                d["progress"] = json.loads(d["progress"])
            except json.JSONDecodeError:
                pass
        return d
