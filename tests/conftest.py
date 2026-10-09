# tests/conftest.py
# Adds project root to sys.path so `from model.xxx import ...` works without
# a package install step.

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
