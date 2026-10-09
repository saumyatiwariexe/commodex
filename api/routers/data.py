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
def get_prices(symbol: str, expiry: Optional[str] = None, from_date: Optional[str] = None, to_date: Optional[str] = None):
    # Mock data for frontend
    return {
        "data": {
            "symbol": symbol,
            "prices": [
                {"date": "2026-10-01", "normalized_price": 6005, "expiry": "04DEC2026"}
            ]
        },
        "meta": {"snapshot_hash": "mock-hash"}
    }

@router.get("/curve")
def get_curve(symbol: str, as_of: str):
    # Mock data for term structure
    return {
        "data": {
            "symbol": symbol,
            "as_of": as_of,
            "curve": [
                {"expiry": "04DEC2026", "price": 6005},
                {"expiry": "05FEB2027", "price": 6050}
            ]
        },
        "meta": {"snapshot_hash": "mock-hash"}
    }
