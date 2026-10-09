from fastapi import APIRouter
from typing import Optional

router = APIRouter(tags=["Analytics"])

@router.get("/pairs")
def get_pairs():
    return {
        "data": [
            {"symbol_a": "GOLDM", "symbol_b": "GOLDPETAL", "expiry_a": "04DEC2026", "expiry_b": "31DEC2026", "gap_days": 27}
        ],
        "meta": {"snapshot_hash": "mock-hash"}
    }

@router.get("/spread")
def get_spread(pair: str, from_date: Optional[str] = None, to_date: Optional[str] = None):
    # Mock data for spread explorer
    return {
        "data": {
            "pair": pair,
            "timeseries": [
                {"date": "2026-10-01", "raw_spread": 15.5, "carry_adj_spread": 12.0, "z_score": 1.5}
            ]
        },
        "meta": {"snapshot_hash": "mock-hash"}
    }

@router.get("/signals")
def get_signals(as_of: str):
    return {
        "data": {
            "signals": [],
            "reason": "no_signal"
        },
        "meta": {"snapshot_hash": "mock-hash"}
    }
