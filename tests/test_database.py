import pytest
import duckdb
import pandas as pd
from datetime import date
from ingestion.models import RawBhavcopy, ValidationResult
from database.ingest_bhavcopy import load_bhavcopy_to_duckdb
from database.setup import setup_databases
import os

@pytest.fixture
def temp_db(tmp_path):
    data_dir = tmp_path / "data"
    setup_databases(str(data_dir))
    return str(data_dir / "commodex.duckdb")

def test_load_bhavcopy_success(temp_db):
    df = pd.DataFrame([{
        "Date": date(2026, 10, 9),
        "Symbol": "GOLDM",
        "ExpiryDate": date(2026, 12, 4),
        "Open": 60000.0,
        "High": 60100.0,
        "Low": 59900.0,
        "Close": 60050.0,
        "Volume": 100,
        "OpenInterest": 500
    }])
    
    raw = RawBhavcopy(requested_date=date(2026, 10, 9), data=df, validation=ValidationResult(is_valid=True))
    
    load_bhavcopy_to_duckdb(raw, temp_db)
    
    conn = duckdb.connect(temp_db)
    res = conn.execute("SELECT * FROM bhav_raw").df()
    conn.close()
    
    assert len(res) == 1
    assert res.iloc[0]["symbol"] == "GOLDM"
    assert res.iloc[0]["close"] == 60050.0
    assert res.iloc[0]["source"] == "local_file"

def test_load_bhavcopy_idempotent(temp_db):
    df = pd.DataFrame([{
        "Date": date(2026, 10, 9),
        "Symbol": "GOLDM",
        "ExpiryDate": date(2026, 12, 4),
        "Open": 60000.0,
        "High": 60100.0,
        "Low": 59900.0,
        "Close": 60050.0,
        "Volume": 100,
        "OpenInterest": 500
    }])
    raw = RawBhavcopy(requested_date=date(2026, 10, 9), data=df, validation=ValidationResult(is_valid=True))
    
    # First load
    load_bhavcopy_to_duckdb(raw, temp_db)
    
    # Update some data
    df.loc[0, "Close"] = 60099.0
    raw = RawBhavcopy(requested_date=date(2026, 10, 9), data=df, validation=ValidationResult(is_valid=True))
    
    # Second load (should update)
    load_bhavcopy_to_duckdb(raw, temp_db)
    
    conn = duckdb.connect(temp_db)
    res = conn.execute("SELECT * FROM bhav_raw").df()
    conn.close()
    
    assert len(res) == 1
    assert res.iloc[0]["close"] == 60099.0
