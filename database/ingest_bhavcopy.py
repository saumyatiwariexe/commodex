import duckdb
import pandas as pd
from datetime import date
from typing import List
from ingestion.models import RawBhavcopy

def load_bhavcopy_to_duckdb(raw: RawBhavcopy, duckdb_path: str = "data/commodex.duckdb"):
    """
    Inserts validated Bhavcopy data into the bhav_raw table in DuckDB.
    """
    if not raw.validation.is_valid:
        raise ValueError(f"Cannot load invalid data: {raw.validation.reason_code}")
        
    if raw.data.empty:
        return
        
    df = raw.data.copy()
    
    # Map columns to schema
    # Schema: trade_date, symbol, expiry_date, open, high, low, close, volume, open_interest, source, ingested_at
    df = df.rename(columns={
        "Date": "trade_date",
        "Symbol": "symbol",
        "ExpiryDate": "expiry_date",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
        "OpenInterest": "open_interest"
    })
    
    df["source"] = "local_file"
    df["ingested_at"] = pd.Timestamp.now()
    
    # We only want columns matching the schema
    cols = ["trade_date", "symbol", "expiry_date", "open", "high", "low", "close", "volume", "open_interest", "source", "ingested_at"]
    df = df[cols]
    
    conn = duckdb.connect(duckdb_path)
    
    # We use INSERT OR REPLACE to ensure idempotency (in case of re-runs on same date)
    try:
        # DuckDB 1.0+ supports INSERT OR REPLACE INTO or ON CONFLICT
        # We can also use a temporary table and then insert with ON CONFLICT
        conn.register("df_temp", df)
        conn.execute("""
            INSERT INTO bhav_raw
            SELECT * FROM df_temp
            ON CONFLICT (trade_date, symbol, expiry_date) DO UPDATE SET
                open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                close = excluded.close,
                volume = excluded.volume,
                open_interest = excluded.open_interest,
                source = excluded.source,
                ingested_at = excluded.ingested_at
        """)
        conn.unregister("df_temp")
    finally:
        conn.close()
