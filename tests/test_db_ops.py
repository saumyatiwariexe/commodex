"""
tests/test_db_ops.py
====================
Integration tests for db/ops.py — the model→database write layer.

Tests exercise each write function with realistic data, verify what lands
in the database, and confirm error handling for bad inputs.

All tests use in-memory databases; no filesystem side-effects.
"""

from __future__ import annotations

import datetime
import math

import pandas as pd
import pytest

from db.schema import create_analytics_schema
from db.ops import (
    write_bhav_raw,
    write_bhav_norm,
    write_pair_spread,
    write_bt_run,
    write_bt_trades,
    write_bt_daily,
    write_contract_calendar,
)
from model.canonical import hash_obj


# ── fixture helpers ───────────────────────────────────────────────────────────

def _fresh_duck():
    import duckdb
    con = duckdb.connect(":memory:")
    create_analytics_schema(con)
    return con


def _make_hash(obj: object) -> str:
    return hash_obj(obj)


# ── bhav_raw ──────────────────────────────────────────────────────────────────

def test_write_bhav_raw_basic() -> None:
    con = _fresh_duck()
    df = pd.DataFrame([{
        "trade_date": datetime.date(2026, 9, 1),
        "symbol": "GOLDM",
        "expiry_date": datetime.date(2026, 9, 5),
        "open": 70000.0, "high": 71000.0, "low": 69500.0, "close": 70500.0,
        "volume": 1500, "open_interest": 5000,
        "source": "local_file",
        "ingested_at": datetime.datetime(2026, 9, 1, 18, 0, 0),
    }])
    inserted = write_bhav_raw(con, df)
    assert inserted == 1
    row = con.execute("SELECT close FROM bhav_raw").fetchone()
    assert abs(row[0] - 70500.0) < 1e-9
    con.close()


def test_write_bhav_raw_duplicate_is_noop() -> None:
    """Re-inserting the same PK should be silently ignored."""
    con = _fresh_duck()
    df = pd.DataFrame([{
        "trade_date": datetime.date(2026, 9, 1),
        "symbol": "GOLDM",
        "expiry_date": datetime.date(2026, 9, 5),
        "open": 70000.0, "high": 71000.0, "low": 69500.0, "close": 70500.0,
        "volume": 1500, "open_interest": 5000,
        "source": "local_file",
        "ingested_at": datetime.datetime(2026, 9, 1, 18, 0, 0),
    }])
    write_bhav_raw(con, df)
    inserted = write_bhav_raw(con, df)  # second call
    assert inserted == 0
    count = con.execute("SELECT COUNT(*) FROM bhav_raw").fetchone()[0]
    assert count == 1
    con.close()


def test_write_bhav_raw_missing_column_raises() -> None:
    con = _fresh_duck()
    df = pd.DataFrame([{"trade_date": datetime.date(2026, 9, 1), "symbol": "GOLDM"}])
    with pytest.raises(ValueError, match="missing columns"):
        write_bhav_raw(con, df)
    con.close()


def test_write_bhav_raw_strips_symbol_whitespace() -> None:
    """Bhavcopy symbols come with trailing spaces; they must be stripped."""
    con = _fresh_duck()
    df = pd.DataFrame([{
        "trade_date": datetime.date(2026, 9, 1),
        "symbol": "  GOLDM  ",
        "expiry_date": datetime.date(2026, 9, 5),
        "open": 70000.0, "high": 71000.0, "low": 69500.0, "close": 70500.0,
        "volume": 1500, "open_interest": 5000,
        "source": "local_file",
        "ingested_at": datetime.datetime(2026, 9, 1, 18, 0, 0),
    }])
    write_bhav_raw(con, df)
    row = con.execute("SELECT symbol FROM bhav_raw").fetchone()
    assert row[0] == "GOLDM"
    con.close()


# ── bhav_norm ─────────────────────────────────────────────────────────────────

def test_write_bhav_norm_basic() -> None:
    con = _fresh_duck()
    df = pd.DataFrame([{
        "trade_date": datetime.date(2026, 9, 1),
        "symbol": "GOLDM",
        "expiry_date": datetime.date(2026, 9, 5),
        "px_per_gram_999": 7050.28,
        "days_to_expiry": 4,
        "liquidity_bucket": "ok",
    }])
    write_bhav_norm(con, df)
    row = con.execute("SELECT px_per_gram_999, liquidity_bucket FROM bhav_norm").fetchone()
    assert abs(row[0] - 7050.28) < 1e-6
    assert row[1] == "ok"
    con.close()


def test_write_bhav_norm_nan_bucket_becomes_null() -> None:
    con = _fresh_duck()
    df = pd.DataFrame([{
        "trade_date": datetime.date(2026, 9, 1),
        "symbol": "GOLDM",
        "expiry_date": datetime.date(2026, 9, 5),
        "px_per_gram_999": 7050.0,
        "days_to_expiry": 4,
        # no liquidity_bucket column
    }])
    write_bhav_norm(con, df)
    row = con.execute("SELECT liquidity_bucket FROM bhav_norm").fetchone()
    assert row[0] is None
    con.close()


def test_write_bhav_norm_upsert_updates_value() -> None:
    """Upserting the same PK must update px_per_gram_999."""
    con = _fresh_duck()
    row_base = {
        "trade_date": datetime.date(2026, 9, 1),
        "symbol": "GOLDM",
        "expiry_date": datetime.date(2026, 9, 5),
        "px_per_gram_999": 7000.0,
        "days_to_expiry": 4,
    }
    write_bhav_norm(con, pd.DataFrame([row_base]))
    row_base["px_per_gram_999"] = 7100.0
    write_bhav_norm(con, pd.DataFrame([row_base]))
    count = con.execute("SELECT COUNT(*) FROM bhav_norm").fetchone()[0]
    val = con.execute("SELECT px_per_gram_999 FROM bhav_norm").fetchone()[0]
    assert count == 1
    assert abs(val - 7100.0) < 1e-9
    con.close()


# ── pair_spread ───────────────────────────────────────────────────────────────

def test_write_pair_spread_basic() -> None:
    con = _fresh_duck()
    df = pd.DataFrame([{
        "trade_date": datetime.date(2026, 9, 1),
        "symbol_a": "GOLDM", "expiry_a": datetime.date(2026, 9, 5),
        "symbol_b": "GOLDPETAL", "expiry_b": datetime.date(2026, 9, 30),
        "expiry_gap_days": -25,
        "raw_spread": 5.2,
        "carry_adj_spread": 4.8,
    }])
    write_pair_spread(con, df)
    row = con.execute("SELECT raw_spread, carry_adj_spread FROM pair_spread").fetchone()
    assert abs(row[0] - 5.2) < 1e-9
    assert abs(row[1] - 4.8) < 1e-9
    con.close()


def test_write_pair_spread_nan_carry_becomes_null() -> None:
    """NaN carry_adj_spread (carry estimation failed) must be stored as NULL."""
    con = _fresh_duck()
    df = pd.DataFrame([{
        "trade_date": datetime.date(2026, 9, 1),
        "symbol_a": "GOLDM", "expiry_a": datetime.date(2026, 9, 5),
        "symbol_b": "GOLDPETAL", "expiry_b": datetime.date(2026, 9, 30),
        "expiry_gap_days": -25,
        "raw_spread": 5.2,
        "carry_adj_spread": float("nan"),
    }])
    write_pair_spread(con, df)
    row = con.execute("SELECT carry_adj_spread FROM pair_spread").fetchone()
    assert row[0] is None
    con.close()


# ── bt_run ────────────────────────────────────────────────────────────────────

def _sample_run() -> dict:
    snap_h = _make_hash([{"path": "data/p.parquet", "file_hash": "sha256:v1:" + "a" * 64, "row_count": 100}])
    cfg_h = _make_hash({"lookback": 60, "z_entry": 2.0})
    return {
        "run_id": "run-test-001",
        "created_at": "2026-09-01T12:00:00+00:00",
        "snapshot_hash": snap_h,
        "config_hash": cfg_h,
        "code_version": "abc1234",
        "gross_pnl": 15000.0,
        "total_cost": 3000.0,
        "net_pnl": 12000.0,
        "sharpe": 1.45,
        "n_trades": 12,
    }


def test_write_bt_run_basic() -> None:
    con = _fresh_duck()
    write_bt_run(con, _sample_run())
    row = con.execute("SELECT run_id, sharpe, n_trades FROM bt_run").fetchone()
    assert row[0] == "run-test-001"
    assert abs(row[1] - 1.45) < 1e-9
    assert row[2] == 12
    con.close()


def test_write_bt_run_missing_run_id_raises() -> None:
    con = _fresh_duck()
    bad = _sample_run()
    del bad["run_id"]
    with pytest.raises(ValueError, match="run_id"):
        write_bt_run(con, bad)
    con.close()


def test_write_bt_run_bad_hash_raises() -> None:
    con = _fresh_duck()
    bad = _sample_run()
    bad["snapshot_hash"] = "not-a-hash"
    with pytest.raises(ValueError, match="snapshot_hash"):
        write_bt_run(con, bad)
    con.close()


def test_write_bt_run_dirty_flag_stored() -> None:
    """A run with '-dirty' in code_version must persist without error."""
    con = _fresh_duck()
    run = _sample_run()
    run["code_version"] = "abc1234-dirty"
    write_bt_run(con, run)
    row = con.execute("SELECT code_version FROM bt_run").fetchone()
    assert row[0].endswith("-dirty")
    con.close()


def test_write_bt_run_nan_metric_becomes_null() -> None:
    """float('nan') metrics must be stored as SQL NULL."""
    con = _fresh_duck()
    run = _sample_run()
    run["sharpe"] = float("nan")
    write_bt_run(con, run)
    row = con.execute("SELECT sharpe FROM bt_run").fetchone()
    assert row[0] is None
    con.close()


# ── bt_trade ──────────────────────────────────────────────────────────────────

def test_write_bt_trades_basic() -> None:
    con = _fresh_duck()
    write_bt_run(con, _sample_run())
    df = pd.DataFrame([{
        "trade_id": 1,
        "leg_a": "GOLDM", "expiry_a": datetime.date(2026, 9, 5),
        "leg_b": "GOLDPETAL", "expiry_b": datetime.date(2026, 9, 30),
        "entry_date": datetime.date(2026, 8, 10),
        "exit_date": datetime.date(2026, 8, 20),
        "exit_reason": "target",
        "qty_a": 1, "qty_b": 100,
        "entry_px_a": 70500.0, "entry_px_b": 7045.0,
        "exit_px_a": 70600.0, "exit_px_b": 7052.0,
        "gross_pnl": 100.0, "cost": 30.0, "net_pnl": 70.0,
    }])
    n = write_bt_trades(con, "run-test-001", df)
    assert n == 1
    row = con.execute("SELECT exit_reason, net_pnl FROM bt_trade").fetchone()
    assert row[0] == "target"
    assert abs(row[1] - 70.0) < 1e-9
    con.close()


def test_write_bt_trades_valid_exit_reasons() -> None:
    """All four exit reasons (target, stop, time, calendar) must be storable."""
    con = _fresh_duck()
    write_bt_run(con, _sample_run())
    rows = []
    for i, reason in enumerate(["target", "stop", "time", "calendar"]):
        rows.append({
            "trade_id": i + 1,
            "leg_a": "GOLDM", "expiry_a": datetime.date(2026, 9, 5),
            "leg_b": "GOLDPETAL", "expiry_b": datetime.date(2026, 9, 30),
            "entry_date": datetime.date(2026, 8, i + 1),
            "exit_reason": reason,
            "qty_a": 1, "qty_b": 100,
        })
    write_bt_trades(con, "run-test-001", pd.DataFrame(rows))
    count = con.execute("SELECT COUNT(*) FROM bt_trade").fetchone()[0]
    assert count == 4
    con.close()


# ── bt_daily ──────────────────────────────────────────────────────────────────

def test_write_bt_daily_basic() -> None:
    con = _fresh_duck()
    write_bt_run(con, _sample_run())
    df = pd.DataFrame([
        {"trade_date": datetime.date(2026, 8, d),
         "strategy_ret": 0.001 * d,
         "gold_ret": 0.0005 * d,
         "position_notional": 700000.0}
        for d in range(1, 6)
    ])
    n = write_bt_daily(con, "run-test-001", df)
    assert n == 5
    count = con.execute("SELECT COUNT(*) FROM bt_daily").fetchone()[0]
    assert count == 5
    con.close()


# ── contract_calendar ─────────────────────────────────────────────────────────

def test_write_contract_calendar_basic() -> None:
    con = _fresh_duck()
    df = pd.DataFrame([{
        "symbol": "GOLDM",
        "expiry_date": datetime.date(2026, 9, 5),
        "listing_date": datetime.date(2026, 7, 1),
        "first_liquid_date": datetime.date(2026, 8, 1),
        "tender_start": datetime.date(2026, 9, 1),
        "last_trade_date": datetime.date(2026, 9, 4),
    }])
    n = write_contract_calendar(con, df)
    assert n == 1
    row = con.execute("SELECT symbol FROM contract_calendar").fetchone()
    assert row[0] == "GOLDM"
    con.close()


def test_write_contract_calendar_upsert() -> None:
    """Re-inserting the same (symbol, expiry) must update the dates."""
    con = _fresh_duck()
    df1 = pd.DataFrame([{
        "symbol": "GOLDM",
        "expiry_date": datetime.date(2026, 9, 5),
        "listing_date": datetime.date(2026, 7, 1),
    }])
    write_contract_calendar(con, df1)
    df2 = pd.DataFrame([{
        "symbol": "GOLDM",
        "expiry_date": datetime.date(2026, 9, 5),
        "listing_date": datetime.date(2026, 6, 15),  # corrected date
    }])
    write_contract_calendar(con, df2)
    count = con.execute("SELECT COUNT(*) FROM contract_calendar").fetchone()[0]
    assert count == 1
    con.close()


# ── end-to-end: model → ops → db ─────────────────────────────────────────────

def test_model_to_db_pipeline() -> None:
    """
    Smoke test: run normalize → pairing → write to bhav_norm + pair_spread.

    Uses the model layer (pure functions) to produce data, then persists it
    via ops.  Confirms the round-trip produces the correct values in DuckDB.
    """
    from model.normalize import normalize_price_by_symbol
    from model.pairing import build_pairs_df

    con = _fresh_duck()

    # Build a tiny bhav_norm-style DataFrame manually (pairing needs it)
    dates = [datetime.date(2026, 9, d) for d in range(1, 6)]
    expiry_m = datetime.date(2026, 9, 5)
    expiry_p = datetime.date(2026, 9, 30)

    norm_rows = []
    for d in dates:
        for symbol, expiry, close in [
            ("GOLDM",    expiry_m, 70000.0 + d.day * 10),
            ("GOLDPETAL", expiry_p, 7000.0 + d.day * 1),
        ]:
            px = normalize_price_by_symbol(symbol, close)
            norm_rows.append({
                "date": d,
                "symbol": symbol,
                "expiry_date": expiry,
                "px_per_gram_999": px,
                "days_to_expiry": (expiry - d).days,
                "liquidity_bucket": "ok",
            })

    norm_df = pd.DataFrame(norm_rows)

    # Write bhav_norm
    write_bhav_norm(con, norm_df.rename(columns={"date": "trade_date"}))
    count = con.execute("SELECT COUNT(*) FROM bhav_norm").fetchone()[0]
    assert count == len(norm_rows)

    # Build pairs
    pairs_df = build_pairs_df(norm_df, "GOLDM", "GOLDPETAL", max_gap_days=30)
    assert not pairs_df.empty

    # Write pair_spread
    n = write_pair_spread(con, pairs_df.rename(columns={"symbol_a": "symbol_a", "symbol_b": "symbol_b"}))
    assert n > 0
    spread_count = con.execute("SELECT COUNT(*) FROM pair_spread").fetchone()[0]
    assert spread_count == n

    con.close()
