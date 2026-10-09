from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional
import pandas as pd


@dataclass
class ValidationResult:
    """Result of validating a Bhavcopy payload."""
    is_valid: bool
    reason_code: Optional[str] = None
    flags: List[str] = field(default_factory=list)


@dataclass
class RawBhavcopy:
    """A parsed but unvalidated raw Bhavcopy dataset."""
    requested_date: date
    data: pd.DataFrame
    validation: ValidationResult = field(
        default_factory=lambda: ValidationResult(is_valid=True)
    )
