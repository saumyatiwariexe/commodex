"""
db/queries.py
=============
Read operations for the FastAPI backend (BACKEND.md §3).

All functions accept an open database connection (DuckDB or SQLite as
appropriate) and return plain Python types (dicts, lists of dicts) ready
for Pydantic validation.
"""

from __future__ import annotations

import datetime
import math
from typing import Any


def _dict_factory(cursor, row: tuple) -> dict[str, Any]:
    """Helper to convert DuckDB row tuple to dict using description."""
    fields = [col[0] for col in cursor.description]
    return dict(zip(fields, row))


# ── DuckDB Queries (Data & Analytics) ─────────────────────────────────────────

def get_contracts(con) -> list[dict[str, Any]]:
    """Return all contract metadata."""
    cur = con.cursor()
    cur.execute("SELECT * FROM contract_meta ORDER BY symbol")
    rows = cur.fetchall()
    return [_dict_factory(cur, row) for row in rows]


def get_prices(
    con,
    symbol: str,
    from_date: datetime.date | str,
    to_date: datetime.date | str,
    expiry: datetime.date | str | None = None,
) -> list[dict[str, Any]]:
    """Return normalised prices for a symbol over a date range.

    If *expiry* is provided, restricts to that specific contract.
    """
    cur = con.cursor()
    query = """
        SELECT trade_date, symbol, expiry_date, px_per_gram_999, days_to_expiry, liquidity_bucket
        FROM bhav_norm
        WHERE symbol = ? AND trade_date >= ? AND trade_date <= ?
    """
    params = [symbol.strip(), str(from_date), str(to_date)]

    if expiry:
        query += " AND expiry_date = ?"
        params.append(str(expiry))

    query += " ORDER BY trade_date, expiry_date"
    cur.execute(query, params)
    return [_dict_factory(cur, row) for row in cur.fetchall()]


def get_curve(con, symbol: str, as_of: datetime.date | str) -> list[dict[str, Any]]:
    """Return term structure (all live expiries) for a symbol on a specific date."""
    cur = con.cursor()
    cur.execute(
        """
        SELECT trade_date, symbol, expiry_date, px_per_gram_999, days_to_expiry, liquidity_bucket
        FROM bhav_norm
        WHERE symbol = ? AND trade_date = ?
        ORDER BY days_to_expiry
        """,
        [symbol.strip(), str(as_of)]
    )
    return [_dict_factory(cur, row) for row in cur.fetchall()]


def get_calendar(
    con,
    from_date: datetime.date | str | None = None,
    to_date: datetime.date | str | None = None,
) -> list[dict[str, Any]]:
    """Return contract lifecycle events."""
    cur = con.cursor()
    query = "SELECT * FROM contract_calendar WHERE 1=1"
    params = []

    if from_date:
        query += " AND expiry_date >= ?"
        params.append(str(from_date))
    if to_date:
        query += " AND expiry_date <= ?"
        params.append(str(to_date))

    query += " ORDER BY expiry_date, symbol"
    cur.execute(query, params)
    return [_dict_factory(cur, row) for row in cur.fetchall()]


def get_pairs(con, as_of: datetime.date | str) -> list[dict[str, Any]]:
    """Return all valid pairs and their gap on a specific date."""
    cur = con.cursor()
    cur.execute(
        """
        SELECT trade_date, leg_a, expiry_a, leg_b, expiry_b, expiry_gap_days, raw_spread, carry_adj_spread
        FROM pair_spread
        WHERE trade_date = ?
        ORDER BY leg_a, expiry_a, leg_b
        """,
        [str(as_of)]
    )
    return [_dict_factory(cur, row) for row in cur.fetchall()]


def get_spread(
    con,
    leg_a: str,
    leg_b: str,
    from_date: datetime.date | str,
    to_date: datetime.date | str,
) -> list[dict[str, Any]]:
    """Return spread history for a specific symbol pair over a date range."""
    cur = con.cursor()
    cur.execute(
        """
        SELECT trade_date, leg_a, expiry_a, leg_b, expiry_b, expiry_gap_days, raw_spread, carry_adj_spread
        FROM pair_spread
        WHERE leg_a = ? AND leg_b = ? AND trade_date >= ? AND trade_date <= ?
        ORDER BY trade_date, expiry_a
        """,
        [leg_a.strip(), leg_b.strip(), str(from_date), str(to_date)]
    )
    return [_dict_factory(cur, row) for row in cur.fetchall()]


def get_backtest_run(con, run_id: str) -> dict[str, Any] | None:
    """Return metadata and metrics for a single backtest run."""
    cur = con.cursor()
    cur.execute("SELECT * FROM bt_run WHERE run_id = ?", [run_id])
    row = cur.fetchone()
    if not row:
        return None
    return _dict_factory(cur, row)


def get_backtest_trades(con, run_id: str) -> list[dict[str, Any]]:
    """Return all trades for a backtest run."""
    cur = con.cursor()
    cur.execute(
        "SELECT * FROM bt_trade WHERE run_id = ? ORDER BY trade_id",
        [run_id]
    )
    return [_dict_factory(cur, row) for row in cur.fetchall()]


def get_backtest_equity(con, run_id: str) -> list[dict[str, Any]]:
    """Return daily equity curve for a backtest run."""
    cur = con.cursor()
    cur.execute(
        "SELECT * FROM bt_daily WHERE run_id = ? ORDER BY trade_date",
        [run_id]
    )
    return [_dict_factory(cur, row) for row in cur.fetchall()]


def get_pairs_for_signals(
    con,
    as_of: datetime.date | str,
    lookback_days: int = 100,
) -> pd.DataFrame:
    """Return historical pair data needed to generate signals up to a specific date.
    
    Joins pair_spread with bhav_norm to get liquidity and DTE.
    Returns a pandas DataFrame ready for model.signal.generate_signals.
    """
    import pandas as pd
    
    query = """
        SELECT 
            p.trade_date, p.leg_a AS symbol_a, p.leg_b AS symbol_b,
            p.expiry_a, p.expiry_b, p.expiry_gap_days,
            p.px_a, p.px_b, p.raw_spread, p.carry_adj_spread,
            b1.liquidity_bucket AS liquidity_a, b2.liquidity_bucket AS liquidity_b,
            b1.days_to_expiry AS dte_a, b2.days_to_expiry AS dte_b
        FROM pair_spread p
        JOIN bhav_norm b1 
          ON p.leg_a = b1.symbol AND p.expiry_a = b1.expiry_date AND p.trade_date = b1.trade_date
        JOIN bhav_norm b2 
          ON p.leg_b = b2.symbol AND p.expiry_b = b2.expiry_date AND p.trade_date = b2.trade_date
        WHERE p.trade_date <= ?
          AND p.trade_date >= (
              SELECT MIN(trade_date) FROM (
                  SELECT DISTINCT trade_date FROM pair_spread 
                  WHERE trade_date <= ? ORDER BY trade_date DESC LIMIT ?
              )
          )
        ORDER BY p.trade_date
    """
    df = con.execute(query, [str(as_of), str(as_of), lookback_days]).df()
    return df

# ── SQLite Queries (App State & Alerts) ───────────────────────────────────────

def get_alerts(
    con,
    from_date: datetime.date | str | None = None,
    to_date: datetime.date | str | None = None,
) -> list[dict[str, Any]]:
    """Return alert history from the SQLite database.

    Note: con is an sqlite3.Connection with row_factory=sqlite3.Row
    """
    query = "SELECT * FROM alert_log WHERE 1=1"
    params = []

    if from_date:
        query += " AND as_of >= ?"
        params.append(str(from_date))
    if to_date:
        query += " AND as_of <= ?"
        params.append(str(to_date))

    query += " ORDER BY as_of DESC, id DESC"
    rows = con.execute(query, params).fetchall()
    return [dict(row) for row in rows]
