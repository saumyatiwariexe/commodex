import pandas as pd
from datetime import date
from typing import IO
from .models import RawBhavcopy

def parse_bhavcopy_csv(requested_date: date, file_obj: IO) -> RawBhavcopy:
    """Parse a raw MCX Bhavcopy CSV file.
    
    Expected columns (minimum):
    - Date
    - ExpiryDate
    - Symbol
    - Open, High, Low, Close
    - Volume, OpenInterest
    """
    df = pd.read_csv(file_obj)
    
    # Standardize column names (strip spaces)
    df.columns = [str(c).strip() for c in df.columns]
    
    # We only care about specific columns, if others exist we ignore them.
    # If required columns are missing, this will raise a KeyError.
    req_cols = ["Date", "ExpiryDate", "Symbol", "Open", "High", "Low", "Close", "Volume", "OpenInterest"]
    for c in req_cols:
        if c not in df.columns:
            # Maybe the CSV has slightly different headers, but the spec assumes these names.
            raise ValueError(f"Missing required column: {c}")

    # Symbol: strip and uppercase
    df["Symbol"] = df["Symbol"].astype(str).str.strip().str.upper()
    
    # Parse dates
    # Date: MM/DD/YYYY
    df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%Y").dt.date
    
    # ExpiryDate: DDMMMYYYY (e.g. 04SEP2026) -> %d%b%Y
    df["ExpiryDate"] = pd.to_datetime(df["ExpiryDate"].astype(str).str.strip().str.upper(), format="%d%b%Y").dt.date
    
    # Prices: float
    for c in ["Open", "High", "Low", "Close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
        # Reject <= 0
        df = df[df[c] > 0]
        
    # Volume, OpenInterest: int (use Int64 for nullable integers)
    for c in ["Volume", "OpenInterest"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
        
    # Drop rows that failed to parse crucial fields (like Date/ExpiryDate NaNs)
    df = df.dropna(subset=["Date", "ExpiryDate", "Symbol"])
    
    return RawBhavcopy(requested_date=requested_date, data=df.reset_index(drop=True))
