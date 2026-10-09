from fastapi import APIRouter, Depends
from typing import Optional
from datetime import date
import duckdb
from ..deps import get_duckdb

router = APIRouter(tags=["Data"])

@router.get("/contracts")
def get_contracts(db: duckdb.DuckDBPyConnection = Depends(get_duckdb)):
    try:
        # Fetch from duckdb
        res = db.execute("SELECT * FROM contract_meta").fetchall()
        columns = [desc[0] for desc in db.description]
        contracts = [dict(zip(columns, row)) for row in res]
        
        return {"data": {"contracts": contracts}, "meta": {"generated_at": date.today().isoformat()}}
    except Exception as e:
        return {"data": {}, "error": {"code": "DB_ERROR", "message": str(e)}}

@router.get("/prices")
def get_prices(symbol: str, expiry: Optional[str] = None, from_date: Optional[str] = None, to_date: Optional[str] = None, db: duckdb.DuckDBPyConnection = Depends(get_duckdb)):
    query = "SELECT trade_date as date, close as price, expiry_date as expiry FROM bhav_raw WHERE symbol = ?"
    params = [symbol]
    
    if expiry:
        query += " AND expiry_date = ?"
        params.append(expiry)
    if from_date:
        query += " AND trade_date >= ?"
        params.append(from_date)
    if to_date:
        query += " AND trade_date <= ?"
        params.append(to_date)
        
    query += " ORDER BY trade_date ASC"
    
    res = db.execute(query, params).fetchall()
    columns = [desc[0] for desc in db.description]
    prices = [dict(zip(columns, row)) for row in res]
    
    # In a real app we might normalize to 999 purity here by joining with contract_meta
    
    return {
        "data": {
            "symbol": symbol,
            "prices": prices
        },
        "meta": {"generated_at": date.today().isoformat()}
    }

@router.get("/curve")
def get_curve(symbol: str, as_of: str, db: duckdb.DuckDBPyConnection = Depends(get_duckdb)):
    query = """
        SELECT expiry_date as expiry, close as price 
        FROM bhav_raw 
        WHERE symbol = ? AND trade_date = ?
        ORDER BY expiry_date ASC
    """
    res = db.execute(query, (symbol, as_of)).fetchall()
    columns = [desc[0] for desc in db.description]
    curve = [dict(zip(columns, row)) for row in res]
    
    return {
        "data": {
            "symbol": symbol,
            "as_of": as_of,
            "curve": curve
        },
        "meta": {"generated_at": date.today().isoformat()}
    }
