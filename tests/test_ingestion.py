import pytest
from datetime import date
from io import StringIO
import pandas as pd
from ingestion.models import RawBhavcopy, ValidationResult
from ingestion.parsers import parse_bhavcopy_csv
from ingestion.validators import validate_bhavcopy
import yaml

@pytest.fixture
def dummy_contracts_meta():
    return {
        "contracts": [
            {"symbol": "GOLDM", "quote_grams": 10},
            {"symbol": "GOLDPETAL", "quote_grams": 1},
        ]
    }

def test_parse_bhavcopy_csv_success():
    csv_data = """Date,ExpiryDate,Symbol,Open,High,Low,Close,Volume,OpenInterest
10/09/2026,04DEC2026, GOLDM ,60000,60100,59900,60050,100,500
10/09/2026,31DEC2026, GOLDPETAL ,6000,6010,5990,6005,1000,5000
"""
    req_date = date(2026, 10, 9)
    raw = parse_bhavcopy_csv(req_date, StringIO(csv_data))
    
    assert raw.requested_date == req_date
    assert len(raw.data) == 2
    assert raw.data.iloc[0]["Symbol"] == "GOLDM"
    assert raw.data.iloc[0]["Date"] == req_date
    assert raw.data.iloc[0]["ExpiryDate"] == date(2026, 12, 4)
    assert raw.data.iloc[0]["Close"] == 60050.0

def test_parse_bhavcopy_missing_columns():
    csv_data = """Date,Symbol,Close\n10/09/2026,GOLDM,60000"""
    with pytest.raises(ValueError, match="Missing required column"):
        parse_bhavcopy_csv(date(2026, 10, 9), StringIO(csv_data))

def test_validate_date_mismatch(dummy_contracts_meta):
    csv_data = """Date,ExpiryDate,Symbol,Open,High,Low,Close,Volume,OpenInterest
10/10/2026,04DEC2026,GOLDM,60000,60100,59900,60050,100,500
"""
    req_date = date(2026, 10, 9) # Requesting 9th, file has 10th
    raw = parse_bhavcopy_csv(req_date, StringIO(csv_data))
    val = validate_bhavcopy(raw, dummy_contracts_meta)
    
    assert val.validation.is_valid is False
    assert val.validation.reason_code == "DATE_MISMATCH"

def test_validate_symbol_filter_and_expiry(dummy_contracts_meta):
    csv_data = """Date,ExpiryDate,Symbol,Open,High,Low,Close,Volume,OpenInterest
10/09/2026,04DEC2026,GOLDM,60000,60100,59900,60050,100,500
10/09/2026,31DEC2026,CRUDEOIL,5000,5100,4900,5050,10,50
"""
    req_date = date(2026, 10, 9)
    raw = parse_bhavcopy_csv(req_date, StringIO(csv_data))
    val = validate_bhavcopy(raw, dummy_contracts_meta)
    
    # CRUDEOIL should be filtered out
    assert len(val.data) == 1
    assert val.data.iloc[0]["Symbol"] == "GOLDM"
    
    # Expiry 04DEC is valid for GOLDM (3rd-5th)
    assert "EXPIRY_WINDOW_VIOLATION" not in val.validation.flags

def test_validate_outlier_flag(dummy_contracts_meta):
    # GOLDM quote=10 -> norm=6005
    # GOLDPETAL quote=1 -> norm=3000 (huge deviation)
    csv_data = """Date,ExpiryDate,Symbol,Open,High,Low,Close,Volume,OpenInterest
10/09/2026,04DEC2026,GOLDM,60000,60100,59900,60050,100,500
10/09/2026,31DEC2026,GOLDPETAL,3000,3010,2990,3005,1000,5000
"""
    req_date = date(2026, 10, 9)
    raw = parse_bhavcopy_csv(req_date, StringIO(csv_data))
    val = validate_bhavcopy(raw, dummy_contracts_meta)
    
    assert val.validation.is_valid is True
    assert "OUTLIER_FLAG" in val.validation.flags
