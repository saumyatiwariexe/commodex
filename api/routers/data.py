from fastapi import APIRouter
from typing import Optional
import yaml
from datetime import date

router = APIRouter(tags=["Data"])

@router.get("/contracts")
def get_contracts():
    try:
        with open("contracts_meta.yaml", "r") as f:
            data = yaml.safe_load(f)
        return {"data": data, "meta": {"generated_at": date.today().isoformat()}}
    except FileNotFoundError:
        return {"data": {}, "error": {"code": "NOT_FOUND", "message": "contracts_meta.yaml not found"}}

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
