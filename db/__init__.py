"""
db/__init__.py
==============
Connection helpers for DuckDB (analytics) and SQLite (app state).

Usage
-----
    from db import analytics_conn, app_conn

    with analytics_conn(":memory:") as con:
        con.execute("SELECT 1")

Both helpers are thin wrappers so callers never import duckdb or sqlite3
directly.  Swap implementations here if the backing store changes.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import duckdb


# ── DuckDB ────────────────────────────────────────────────────────────────────

@contextmanager
def analytics_conn(path: str | Path = ":memory:") -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """Yield a DuckDB connection, closing it on exit.

    Args:
        path: Filesystem path for a persistent database, or ``":memory:"``
              for an in-process database (useful in tests).

    Yields:
        An open :class:`duckdb.DuckDBPyConnection`.
    """
    con = duckdb.connect(str(path))
    try:
        yield con
    finally:
        con.close()


# ── SQLite ────────────────────────────────────────────────────────────────────

@contextmanager
def app_conn(path: str | Path = ":memory:") -> Generator[sqlite3.Connection, None, None]:
    """Yield a SQLite connection with WAL mode and row_factory set.

    Args:
        path: Filesystem path for a persistent database, or ``":memory:"``
              for an in-process database (useful in tests).

    Yields:
        An open :class:`sqlite3.Connection` with ``row_factory = sqlite3.Row``.
    """
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    # WAL is better for concurrent readers on the same file
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
