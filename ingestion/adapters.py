from typing import Protocol
from datetime import date
from pathlib import Path
from .models import RawBhavcopy, ValidationResult
from .parsers import parse_bhavcopy_csv
import pandas as pd

class BhavcopySource(Protocol):
    def fetch(self, requested: date) -> RawBhavcopy: ...

class LocalFilesSource:
    """Reads Bhavcopy CSVs from a local directory (e.g., data/inbox)."""
    
    def __init__(self, inbox_dir: str):
        self.inbox_dir = Path(inbox_dir)
        
    def fetch(self, requested: date) -> RawBhavcopy:
        # Expected filename format: bhavcopy_YYYY-MM-DD.csv
        filename = f"bhavcopy_{requested.isoformat()}.csv"
        file_path = self.inbox_dir / filename
        
        if not file_path.exists():
            return RawBhavcopy(
                requested_date=requested,
                data=pd.DataFrame(),
                validation=ValidationResult(is_valid=False, reason_code="FILE_NOT_FOUND")
            )
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return parse_bhavcopy_csv(requested, f)
        except Exception as e:
            return RawBhavcopy(
                requested_date=requested,
                data=pd.DataFrame(),
                validation=ValidationResult(is_valid=False, reason_code=f"PARSE_ERROR: {str(e)}")
            )
