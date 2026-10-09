"""
tests/test_canonical.py
=======================
Unit tests for model/canonical.py (MODEL.md §12).

Rules verified:
  - Keys sorted recursively.
  - Separators: no whitespace.
  - Floats: shortest round-trip, -0.0 → 0.0.
  - NaN / inf rejected.
  - Naive datetime rejected; UTC-aware accepted.
  - date → ISO string.
  - Sets → sorted list.
  - hash_obj returns "sha256:v1:<64-hex>".
  - snapshot_hash sorts by path.
  - canonical_bytes is deterministic.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import math
import tempfile
from pathlib import Path

import pytest

from model.canonical import canonical_bytes, hash_file, hash_obj, snapshot_hash


# ── canonical_bytes ───────────────────────────────────────────────────────────

class TestCanonicalBytes:
    def test_none(self) -> None:
        assert canonical_bytes(None) == b"null"

    def test_bool_true(self) -> None:
        assert canonical_bytes(True) == b"true"

    def test_bool_false(self) -> None:
        assert canonical_bytes(False) == b"false"

    def test_int(self) -> None:
        assert canonical_bytes(42) == b"42"

    def test_float_basic(self) -> None:
        result = json.loads(canonical_bytes(1.5))
        assert result == 1.5

    def test_float_negative_zero_normalised(self) -> None:
        """−0.0 must be written as 0.0."""
        result = json.loads(canonical_bytes(-0.0))
        assert result == 0.0
        assert math.copysign(1.0, result) == 1.0  # not negative zero

    def test_float_nan_rejected(self) -> None:
        with pytest.raises(ValueError, match="non-finite"):
            canonical_bytes(float("nan"))

    def test_float_inf_rejected(self) -> None:
        with pytest.raises(ValueError, match="non-finite"):
            canonical_bytes(float("inf"))

    def test_float_neginf_rejected(self) -> None:
        with pytest.raises(ValueError, match="non-finite"):
            canonical_bytes(float("-inf"))

    def test_string(self) -> None:
        assert canonical_bytes("hello") == b'"hello"'

    def test_dict_keys_sorted(self) -> None:
        obj = {"z": 1, "a": 2, "m": 3}
        parsed = json.loads(canonical_bytes(obj))
        assert list(parsed.keys()) == ["a", "m", "z"]

    def test_nested_dict_keys_sorted(self) -> None:
        obj = {"outer_z": {"inner_b": 1, "inner_a": 2}, "outer_a": 0}
        parsed = json.loads(canonical_bytes(obj))
        assert list(parsed.keys()) == ["outer_a", "outer_z"]
        assert list(parsed["outer_z"].keys()) == ["inner_a", "inner_b"]

    def test_no_whitespace_separators(self) -> None:
        raw = canonical_bytes({"a": 1, "b": 2}).decode()
        assert " " not in raw

    def test_list_order_preserved(self) -> None:
        obj = [3, 1, 2]
        assert json.loads(canonical_bytes(obj)) == [3, 1, 2]

    def test_set_becomes_sorted_list(self) -> None:
        obj = {3, 1, 2}
        assert json.loads(canonical_bytes(obj)) == [1, 2, 3]

    def test_frozenset_becomes_sorted_list(self) -> None:
        obj = frozenset(["banana", "apple", "cherry"])
        assert json.loads(canonical_bytes(obj)) == ["apple", "banana", "cherry"]

    def test_tuple_order_preserved(self) -> None:
        assert json.loads(canonical_bytes((10, 20, 30))) == [10, 20, 30]

    def test_date_iso_format(self) -> None:
        d = datetime.date(2026, 10, 9)
        assert json.loads(canonical_bytes(d)) == "2026-10-09"

    def test_datetime_utc_accepted(self) -> None:
        dt = datetime.datetime(2026, 10, 9, 12, 0, 0, tzinfo=datetime.timezone.utc)
        result = json.loads(canonical_bytes(dt))
        assert "2026-10-09" in result

    def test_datetime_naive_rejected(self) -> None:
        dt = datetime.datetime(2026, 10, 9, 12, 0, 0)  # naive
        with pytest.raises(ValueError, match="naive datetime"):
            canonical_bytes(dt)

    def test_unsupported_type_raises(self) -> None:
        with pytest.raises(TypeError):
            canonical_bytes(object())

    def test_deterministic(self) -> None:
        obj = {"b": [3, 1, 2], "a": {"y": None, "x": 1.5}}
        assert canonical_bytes(obj) == canonical_bytes(obj)

    def test_utf8_no_bom(self) -> None:
        result = canonical_bytes({"emoji": "🏅"})
        assert not result.startswith(b"\xef\xbb\xbf")  # no UTF-8 BOM


# ── hash_obj ──────────────────────────────────────────────────────────────────

class TestHashObj:
    def test_format(self) -> None:
        h = hash_obj({"key": "value"})
        prefix, version, digest = h.split(":")
        assert prefix == "sha256"
        assert version == "v1"
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)

    def test_matches_manual_sha256(self) -> None:
        obj = {"a": 1}
        expected_digest = hashlib.sha256(canonical_bytes(obj)).hexdigest()
        assert hash_obj(obj) == f"sha256:v1:{expected_digest}"

    def test_different_objects_differ(self) -> None:
        assert hash_obj({"a": 1}) != hash_obj({"a": 2})

    def test_key_order_irrelevant(self) -> None:
        """Two dicts with the same k/v pairs but different insertion order
        must produce the same hash because keys are sorted."""
        obj1 = {"z": 1, "a": 2}
        obj2 = {"a": 2, "z": 1}
        assert hash_obj(obj1) == hash_obj(obj2)


# ── hash_file ─────────────────────────────────────────────────────────────────

class TestHashFile:
    def test_format_and_content(self, tmp_path: Path) -> None:
        f = tmp_path / "sample.bin"
        f.write_bytes(b"hello world")
        h = hash_file(f)
        prefix, version, digest = h.split(":")
        assert prefix == "sha256"
        assert version == "v1"
        expected = hashlib.sha256(b"hello world").hexdigest()
        assert digest == expected

    def test_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.bin"
        f.write_bytes(b"")
        h = hash_file(f)
        assert h == f"sha256:v1:{hashlib.sha256(b'').hexdigest()}"


# ── snapshot_hash ─────────────────────────────────────────────────────────────

class TestSnapshotHash:
    def _entry(self, path: str, digest: str = "abc", rows: int = 10) -> dict:
        return {"path": path, "file_hash": f"sha256:v1:{digest}", "row_count": rows}

    def test_sorted_by_path(self) -> None:
        """Entries in different order should produce the same hash."""
        e1 = self._entry("data/raw/2026-01-01.parquet")
        e2 = self._entry("data/raw/2026-01-02.parquet")
        assert snapshot_hash([e1, e2]) == snapshot_hash([e2, e1])

    def test_different_entries_differ(self) -> None:
        e1 = self._entry("data/raw/2026-01-01.parquet", digest="aaa")
        e2 = self._entry("data/raw/2026-01-01.parquet", digest="bbb")
        assert snapshot_hash([e1]) != snapshot_hash([e2])

    def test_format(self) -> None:
        h = snapshot_hash([self._entry("a.parquet")])
        prefix, version, digest = h.split(":")
        assert prefix == "sha256"
        assert version == "v1"
        assert len(digest) == 64
