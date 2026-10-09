import duckdb
import sqlite3
from typing import Generator
from fastapi import Request
from .config import settings

def get_duckdb() -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """Dependency for getting a DuckDB connection."""
    # DuckDB can have multiple read connections, but typically we just connect.
    # In a real app we might use a connection pool or read-only mode for the API.
    conn = duckdb.connect(settings.DUCKDB_PATH, read_only=True)
    try:
        yield conn
    finally:
        conn.close()

def get_sqlite() -> Generator[sqlite3.Connection, None, None]:
    """Dependency for getting a SQLite connection."""
    conn = sqlite3.connect(settings.SQLITE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
