"""
pipeline/ingest.py
==================
Data ingestion pipeline. Fetches, parses, validates, and stores Bhavcopy data.
"""

import datetime
import hashlib
import json
import logging
from pathlib import Path

import pandas as pd
import yaml

from db import analytics_conn
from db.ops import write_bhav_raw, write_bhav_norm
from pipeline.adapters import BhavcopySource

logger = logging.getLogger(__name__)

def load_contracts_meta() -> dict:
    with open("contracts_meta.yaml", "r") as f:
        meta = yaml.safe_load(f)
    return {c["symbol"]: c for c in meta["contracts"]}


def parse_bhavcopy(raw_data: bytes, format: str) -> pd.DataFrame:
    import io
    
    if format == "csv":
        df = pd.read_csv(io.BytesIO(raw_data))
    elif format == "excel":
        df = pd.read_excel(io.BytesIO(raw_data))
    else:
        raise ValueError(f"Unknown format: {format}")
        
    df.columns = [str(c).strip() for c in df.columns]
    return df


def process_bhavcopy(requested_date: datetime.date, df: pd.DataFrame, source_name: str, meta: dict) -> pd.DataFrame | None:
    # 1. Date echo check
    if "Date" not in df.columns:
        logger.error("DATE_MISMATCH: Missing 'Date' column")
        return None
        
    # parse date explicitly with %m/%d/%Y
    df["DateParsed"] = pd.to_datetime(df["Date"], format="%m/%d/%Y", errors="coerce").dt.date
    if df["DateParsed"].isna().all():
        logger.error("DATE_MISMATCH: Cannot parse Date column")
        return None
        
    actual_date = df["DateParsed"].dropna().iloc[0]
    if actual_date != requested_date:
        logger.error(f"DATE_MISMATCH: requested {requested_date}, got {actual_date}")
        return None

    # 2. Symbol filter
    allowed_symbols = set(meta.keys())
    if "Symbol" not in df.columns:
        return None
        
    df["Symbol"] = df["Symbol"].astype(str).str.strip().str.upper()
    df = df[df["Symbol"].isin(allowed_symbols)].copy()

    if df.empty:
        logger.warning(f"No allowed symbols found for {requested_date}")
        return None

    # ExpiryDate
    if "ExpiryDate" in df.columns:
        # Expected %d%b%Y e.g. 04SEP2026
        df["ExpiryDateParsed"] = pd.to_datetime(df["ExpiryDate"], format="%d%b%Y", errors="coerce").dt.date
    else:
        df["ExpiryDateParsed"] = pd.NaT

    # Map prices
    price_cols = {"Open": "open", "High": "high", "Low": "low", "Close": "close"}
    for k, v in price_cols.items():
        if k in df.columns:
            df[v] = pd.to_numeric(df[k], errors="coerce")
            df.loc[df[v] <= 0, v] = pd.NA
        else:
            df[v] = pd.NA
            
    # Volume and OpenInterest
    for col, out_col in [("Volume", "volume"), ("OpenInterest", "open_interest")]:
        if col in df.columns:
            df[out_col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
        else:
            df[out_col] = 0

    df["trade_date"] = requested_date
    df["expiry_date"] = df["ExpiryDateParsed"]
    df["source"] = source_name
    df["ingested_at"] = datetime.datetime.now(datetime.timezone.utc)
    
    # Check duplicates
    df = df.drop_duplicates(subset=["trade_date", "Symbol", "expiry_date"])
    
    res_df = df[["trade_date", "Symbol", "expiry_date", "open", "high", "low", "close", "volume", "open_interest", "source", "ingested_at"]].copy()
    res_df = res_df.rename(columns={"Symbol": "symbol"})
    
    # Basic validation drops rows with missing key prices or dates
    res_df = res_df.dropna(subset=["expiry_date", "close"])
    
    return res_df


def save_raw_parquet(df: pd.DataFrame, requested_date: datetime.date, source_name: str, base_dir: Path):
    date_str = requested_date.isoformat()
    out_dir = base_dir / "raw" / f"date={date_str}"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    part_path = out_dir / "part.parquet"
    if part_path.exists():
        logger.info(f"Parquet already exists for {date_str}, skipping overwrite.")
        return
        
    df.to_parquet(part_path, index=False)
    
    data_bytes = part_path.read_bytes()
    sha256 = hashlib.sha256(data_bytes).hexdigest()
    
    manifest_path = out_dir / "manifest.json"
    manifest = {
        "source": source_name,
        "fetch_time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "row_count": len(df),
        "sha256": sha256
    }
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)


def run_ingestion(source: BhavcopySource, requested_date: datetime.date, data_dir: str | Path, duckdb_path: str):
    data_dir = Path(data_dir)
    meta = load_contracts_meta()
    
    raw = source.fetch(requested_date)
    if not raw:
        logger.info(f"No data fetched for {requested_date}")
        return False
        
    df = parse_bhavcopy(raw.data, raw.format)
    processed = process_bhavcopy(requested_date, df, raw.source_name, meta)
    
    if processed is None or processed.empty:
        logger.info(f"No valid data to ingest for {requested_date}")
        return False
        
    save_raw_parquet(processed, requested_date, raw.source_name, data_dir)
    
    with analytics_conn(duckdb_path) as con:
        inserted = write_bhav_raw(con, processed)
        
        # We also need to normalize.
        from model.normalize import normalize_df
        norm_df = normalize_df(processed, meta)
        if not norm_df.empty:
            norm_df["days_to_expiry"] = (pd.to_datetime(norm_df["expiry_date"]) - pd.to_datetime(norm_df["trade_date"])).dt.days
            write_bhav_norm(con, norm_df)
            
    return inserted > 0
