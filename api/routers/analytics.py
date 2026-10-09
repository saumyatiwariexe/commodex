from fastapi import APIRouter, Depends
from typing import Optional
from datetime import date
import duckdb
from ..deps import get_duckdb

router = APIRouter(tags=["Analytics"])

@router.get("/pairs")
def get_pairs(db: duckdb.DuckDBPyConnection = Depends(get_duckdb)):
    # Since pair_spread isn't populated yet, we'll try to query it but return empty if no data
    query = "SELECT DISTINCT leg_a as symbol_a, leg_b as symbol_b, expiry_a, expiry_b, expiry_gap_days as gap_days FROM pair_spread"
    res = db.execute(query).fetchall()
    columns = [desc[0] for desc in db.description]
    pairs = [dict(zip(columns, row)) for row in res]
    
    return {
        "data": pairs,
        "meta": {"generated_at": date.today().isoformat()}
    }

@router.get("/spread")
def get_spread(pair: str, from_date: Optional[str] = None, to_date: Optional[str] = None, db: duckdb.DuckDBPyConnection = Depends(get_duckdb)):
    try:
        symbol_a, symbol_b = pair.split("-")
    except ValueError:
        return {"data": {}, "error": {"code": "INVALID_PAIR", "message": "Pair must be separated by '-' e.g. GOLDM-GOLDTEN"}}

    query = "SELECT trade_date as date, raw_spread, carry_adj_spread FROM pair_spread WHERE leg_a = ? AND leg_b = ?"
    params = [symbol_a, symbol_b]
    
    if from_date:
        query += " AND trade_date >= ?"
        params.append(from_date)
    if to_date:
        query += " AND trade_date <= ?"
        params.append(to_date)
        
    query += " ORDER BY trade_date ASC"
    
    res = db.execute(query, params).fetchall()
    columns = [desc[0] for desc in db.description]
    timeseries = [dict(zip(columns, row)) for row in res]
    
    # We don't have z_score in table, we might compute it on fly or let model populate it
    
    return {
        "data": {
            "pair": pair,
            "timeseries": timeseries
        },
        "meta": {"generated_at": date.today().isoformat()}
    }

@router.get("/signals")
def get_signals(as_of: str, db: duckdb.DuckDBPyConnection = Depends(get_duckdb)):
    # Mocking signals slightly still since signals aren't stored in a specific signal table in schema.
    # Architecture says they run on demand or from backtest.
    return {
        "data": {
            "signals": [],
            "reason": "no_signals_generated_for_date"
        },
        "meta": {"generated_at": date.today().isoformat()}
    }
