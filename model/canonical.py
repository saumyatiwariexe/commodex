"""
model/canonical.py
==================
Canonical serialisation and hashing for reproducibility (MODEL.md §12).

Rules (§12.2):
  - JSON, UTF-8, no BOM.
  - Object keys sorted recursively.
  - Separators ","  and ":" with no whitespace.
  - Integers as integers; floats via shortest round-trip (no -0.0).
  - Reject NaN and infinity.
  - date / datetime → ISO-8601 string (datetime must be UTC-aware or explicit UTC).
  - Sets / frozensets → sorted lists. Ordered sequences keep order.
  - Null written explicitly.
  - No machine-specific values (no absolute paths, hostnames, etc.).
  - Version tag "v1" in the stored string. Bump to "v2" if these rules change.

Public API
----------
  canonical_bytes(obj) -> bytes
  hash_obj(obj)        -> str   e.g. "sha256:v1:<64 hex chars>"
  hash_file(path)      -> str   stream file in fixed-size chunks
"""

from __future__ import annotations

import datetime
import hashlib
import json
import math
from pathlib import Path
from typing import Any

# ── version ──────────────────────────────────────────────────────────────────
_CANON_VERSION = "v1"
_CHUNK_SIZE = 1 << 20  # 1 MiB


# ── internal helpers ──────────────────────────────────────────────────────────

def _prepare(obj: Any) -> Any:  # noqa: ANN401
    """Recursively convert *obj* into a JSON-safe structure.

    Raises ``ValueError`` for NaN / infinity, and for datetime objects that
    are not UTC-aware (naïve datetimes are ambiguous and therefore rejected).
    """
    if obj is None or isinstance(obj, bool):
        return obj
    if isinstance(obj, int):
        return obj
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            raise ValueError(f"canonical_bytes: rejecting non-finite float: {obj!r}")
        # normalise -0.0 → 0.0
        return 0.0 if obj == 0.0 else obj
    if isinstance(obj, str):
        return obj
    if isinstance(obj, datetime.datetime):
        if obj.tzinfo is None:
            raise ValueError(
                "canonical_bytes: naive datetime rejected; make it UTC-aware "
                f"(e.g. datetime.timezone.utc): {obj!r}"
            )
        return obj.isoformat()
    if isinstance(obj, datetime.date):
        return obj.isoformat()          # "2026-10-09"
    if isinstance(obj, (set, frozenset)):
        return sorted(_prepare(v) for v in obj)
    if isinstance(obj, (list, tuple)):
        return [_prepare(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _prepare(v) for k, v in sorted(obj.items())}
    raise TypeError(f"canonical_bytes: unsupported type {type(obj).__name__!r}: {obj!r}")


# ── public functions ──────────────────────────────────────────────────────────

def canonical_bytes(obj: Any) -> bytes:  # noqa: ANN401
    """Return the canonical UTF-8 JSON encoding of *obj*.

    Keys are sorted, separators are ``","`` and ``":"``, and floats are
    encoded with Python's shortest round-trip form.  The result is
    deterministic across Python processes, platforms and versions of this
    function (as long as the version tag stays at ``v1``).

    Raises ``ValueError`` for NaN/infinity or naïve datetime objects.
    Raises ``TypeError`` for unsupported types.
    """
    prepared = _prepare(obj)
    return json.dumps(prepared, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def hash_obj(obj: Any) -> str:  # noqa: ANN401
    """Return ``"sha256:v1:<64-hex-char-digest>"`` for *obj*.

    Always go through this function.  Never call ``json.dumps`` +
    ``hashlib.sha256`` directly (MODEL.md §12.2, AGENTS.md §7).
    """
    digest = hashlib.sha256(canonical_bytes(obj)).hexdigest()
    return f"sha256:{_CANON_VERSION}:{digest}"


def hash_file(path: Path | str) -> str:
    """Return ``"sha256:v1:<digest>"`` for the raw bytes of *path*.

    Reads the file in 1 MiB chunks so large Parquet files don't exhaust RAM.
    The file must exist and be readable; caller is responsible for that.
    """
    path = Path(path)
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(_CHUNK_SIZE):
            h.update(chunk)
    return f"sha256:{_CANON_VERSION}:{h.hexdigest()}"


def snapshot_hash(entries: list[dict[str, Any]]) -> str:
    """Compute the snapshot hash from a list of partition manifest entries.

    Each entry must contain:
      - ``"path"``      (str)  relative POSIX path of the Parquet file
      - ``"file_hash"`` (str)  sha256:v1:… returned by :func:`hash_file`
      - ``"row_count"`` (int)  number of rows written

    Entries are sorted by path before hashing, matching MODEL.md §12.4.
    """
    sorted_entries = sorted(entries, key=lambda e: e["path"])
    return hash_obj(sorted_entries)
