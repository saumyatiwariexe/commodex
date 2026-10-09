from typing import Dict, Any
from .models import RawBhavcopy, ValidationResult
import pandas as pd
import numpy as np

def validate_bhavcopy(raw: RawBhavcopy, contracts_meta: Dict[str, Any], price_band_pct: float = 0.05) -> RawBhavcopy:
    """Validate and clean the raw Bhavcopy dataset according to DATA_PIPELINE.md rules."""
    
    if raw.data.empty:
        raw.validation = ValidationResult(is_valid=False, reason_code="EMPTY_DATA")
        return raw

    df = raw.data.copy()
    flags = []
    
    # 1. Date echo check
    unique_dates = df["Date"].unique()
    if len(unique_dates) != 1 or unique_dates[0] != raw.requested_date:
        raw.validation = ValidationResult(is_valid=False, reason_code="DATE_MISMATCH")
        return raw
        
    # 2. Symbol filter
    allowed_symbols = {c["symbol"] for c in contracts_meta.get("contracts", [])}
    if not allowed_symbols:
        allowed_symbols = {"GOLDM", "GOLDTEN", "GOLDGUINEA", "GOLDPETAL"}
    df = df[df["Symbol"].isin(allowed_symbols)].copy()
    
    if df.empty:
        raw.validation = ValidationResult(is_valid=False, reason_code="NO_ALLOWED_SYMBOLS")
        return raw
        
    # 3. Duplicate check
    dups = df.duplicated(subset=["Symbol", "ExpiryDate", "Date"])
    if dups.any():
        df = df.drop_duplicates(subset=["Symbol", "ExpiryDate", "Date"])
        flags.append("DUPLICATES_REMOVED")
        
    # 4. Expiry window check
    # GOLDM 3rd-5th, others 27th-31st
    def check_expiry(row):
        sym = row["Symbol"]
        day = row["ExpiryDate"].day
        if sym == "GOLDM":
            return 3 <= day <= 5
        else:
            return 27 <= day <= 31
            
    expiry_valid = df.apply(check_expiry, axis=1)
    if not expiry_valid.all():
        flags.append("EXPIRY_WINDOW_VIOLATION")
        
    # 5. Sanity band (normalized price within band of day's median)
    # First, build a map of quote_grams
    quote_map = {c["symbol"]: c["quote_grams"] for c in contracts_meta.get("contracts", [])}
    
    def normalize_price(row):
        qg = quote_map.get(row["Symbol"], 1.0)
        return row["Close"] / qg
        
    df["norm_close"] = df.apply(normalize_price, axis=1)
    day_median = df["norm_close"].median()
    
    # Check if any price deviates by more than price_band_pct from median
    deviations = np.abs(df["norm_close"] - day_median) / day_median
    if (deviations > price_band_pct).any():
        flags.append("OUTLIER_FLAG")
        
    df = df.drop(columns=["norm_close"])
    
    raw.data = df
    raw.validation = ValidationResult(is_valid=True, flags=flags)
    
    return raw
