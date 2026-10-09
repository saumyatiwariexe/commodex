"""
pipeline/adapters.py
====================
Adapters for fetching Bhavcopy data (DATA_PIPELINE.md §1).
"""

import datetime
import logging
from pathlib import Path
from typing import Protocol
import pandas as pd

logger = logging.getLogger(__name__)

class RawBhavcopy:
    def __init__(self, data: bytes, source_name: str, format: str):
        self.data = data
        self.source_name = source_name
        self.format = format # "csv" or "excel"

class BhavcopySource(Protocol):
    def fetch(self, requested: datetime.date) -> RawBhavcopy | None: ...


class LocalFilesSource:
    """Reads Bhavcopy from a local inbox directory."""
    def __init__(self, inbox_dir: str | Path):
        self.inbox_dir = Path(inbox_dir)
        self.inbox_dir.mkdir(parents=True, exist_ok=True)

    def fetch(self, requested: datetime.date) -> RawBhavcopy | None:
        """Looks for a file matching the requested date in the inbox.
        
        Expected formats:
        - bhavcopy_YYYY-MM-DD.csv
        - bhavcopy_YYYY-MM-DD.xlsx
        """
        date_str = requested.isoformat()
        
        for fmt, ext in [("csv", ".csv"), ("excel", ".xlsx")]:
            candidate = self.inbox_dir / f"bhavcopy_{date_str}{ext}"
            if candidate.exists():
                logger.info(f"LocalFilesSource found {candidate}")
                return RawBhavcopy(candidate.read_bytes(), "local_file", fmt)
        
        logger.debug(f"LocalFilesSource found no file for {date_str}")
        return None


class MCXLiveSource:
    """Fetches Bhavcopy from MCX live endpoint."""
    def __init__(self):
        # Unverified implementation (DATA_PIPELINE.md §0)
        # We need a cURL capture before we can implement the exact payload.
        # Stubbing out for now.
        pass

    def fetch(self, requested: datetime.date) -> RawBhavcopy | None:
        # TODO: Implement live fetching logic.
        logger.warning("MCXLiveSource is currently unverified. Using fallback.")
        return None
