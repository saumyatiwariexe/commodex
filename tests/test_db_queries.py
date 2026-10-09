"""
tests/test_db_queries.py
========================
Tests for db/queries.py (Backend API reads).
"""

from __future__ import annotations

import datetime

import pandas as pd
import pytest

from db.schema import create_analytics_schema, create_app_schema
from db.ops import (
    write_bhav_norm,
    write_pair_spread,
    write_bt_run,
    write_bt_trades,
    write_bt_daily,
    write_contract_calendar,
)
from db.queries import (
    get_contracts,
    get_prices,
    get_curve,
    get_calendar,
    get_pairs,
    get_spread,
    get_backtest_run,
    get_backtest_trades,
    get_backtest_equity,
    get_alerts,
)
from model.canonical import hash_obj


def _fresh_duck():
    import duckdb
    con = duckdb.connect(":memory:")
    create_analytics_schema(con)
    return con


def _fresh_lite():
    import sqlite3
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    create_app_schema(con)
    return con


def _make_hash(obj: object) -> str:
    return hash_obj(obj)


def test_get_contracts() -> None:
    con = _fresh_duck()
    con.execute("INSERT INTO contract_meta VALUES ('GOLDM', 100, 10, 995, '3rd-5th')")
    rows = get_contracts(con)
    assert len(rows) == 1
    assert rows[0]["symbol"] == "GOLDM"
    assert rows[0]["lot_grams"] == 100.0
    con.close()


def test_get_prices() -> None:
    con = _fresh_duck()
    df = pd.DataFrame([{
        "trade_date": datetime.date(2026, 9, 1),
        "symbol": "GOLDM",
        "expiry_date": datetime.date(2026, 9, 5),
        "px_per_gram_999": 7050.0,
        "days_to_expiry": 4,
        "liquidity_bucket": "ok",
    }, {
        "trade_date": datetime.date(2026, 9, 2),
        "symbol": "GOLDM",
        "expiry_date": datetime.date(2026, 9, 5),
        "px_per_gram_999": 7060.0,
        "days_to_expiry": 3,
        "liquidity_bucket": "ok",
    }])
    write_bhav_norm(con, df)
    
    res = get_prices(con, "GOLDM", "2026-09-01", "2026-09-02")
    assert len(res) == 2
    
    res = get_prices(con, "GOLDM", "2026-09-01", "2026-09-02", expiry="2026-09-05")
    assert len(res) == 2
    
    res = get_prices(con, "GOLDM", "2026-09-01", "2026-09-02", expiry="2026-10-05")
    assert len(res) == 0
    con.close()


def test_get_curve() -> None:
    con = _fresh_duck()
    df = pd.DataFrame([{
        "trade_date": datetime.date(2026, 9, 1),
        "symbol": "GOLDM",
        "expiry_date": datetime.date(2026, 9, 5),
        "px_per_gram_999": 7050.0,
        "days_to_expiry": 4,
    }, {
        "trade_date": datetime.date(2026, 9, 1),
        "symbol": "GOLDM",
        "expiry_date": datetime.date(2026, 10, 5),
        "px_per_gram_999": 7100.0,
        "days_to_expiry": 34,
    }])
    write_bhav_norm(con, df)
    
    res = get_curve(con, "GOLDM", "2026-09-01")
    assert len(res) == 2
    assert res[0]["expiry_date"] == datetime.date(2026, 9, 5) # ordered by days_to_expiry
    con.close()


def test_get_calendar() -> None:
    con = _fresh_duck()
    df = pd.DataFrame([{
        "symbol": "GOLDM",
        "expiry_date": datetime.date(2026, 9, 5),
        "listing_date": datetime.date(2026, 7, 1),
    }])
    write_contract_calendar(con, df)
    
    res = get_calendar(con, from_date="2026-09-01", to_date="2026-09-30")
    assert len(res) == 1
    assert res[0]["symbol"] == "GOLDM"
    con.close()


def test_get_pairs_and_spread() -> None:
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
    
    res = get_pairs(con, "2026-09-01")
    assert len(res) == 1
    assert res[0]["leg_a"] == "GOLDM"
    
    res = get_spread(con, "GOLDM", "GOLDPETAL", "2026-09-01", "2026-09-01")
    assert len(res) == 1
    assert res[0]["raw_spread"] == 5.2
    con.close()


def test_get_backtest() -> None:
    con = _fresh_duck()
    run = {
        "run_id": "run1",
        "created_at": "2026-09-01T12:00:00+00:00",
        "snapshot_hash": _make_hash([]),
        "config_hash": _make_hash({}),
        "code_version": "abc",
        "sharpe": 1.5
    }
    write_bt_run(con, run)
    
    trade_df = pd.DataFrame([{
        "trade_id": 1,
        "leg_a": "A", "expiry_a": datetime.date(2026, 9, 5),
        "leg_b": "B", "expiry_b": datetime.date(2026, 9, 30),
        "entry_date": datetime.date(2026, 8, 10),
        "qty_a": 1, "qty_b": 100,
    }])
    write_bt_trades(con, "run1", trade_df)
    
    daily_df = pd.DataFrame([{
        "trade_date": datetime.date(2026, 8, 10),
        "strategy_ret": 0.001,
        "gold_ret": 0.0005,
    }])
    write_bt_daily(con, "run1", daily_df)
    
    res_run = get_backtest_run(con, "run1")
    assert res_run is not None
    assert res_run["sharpe"] == 1.5
    
    res_trades = get_backtest_trades(con, "run1")
    assert len(res_trades) == 1
    
    res_equity = get_backtest_equity(con, "run1")
    assert len(res_equity) == 1
    assert res_equity[0]["strategy_ret"] == 0.001
    
    con.close()


def test_get_alerts() -> None:
    con = _fresh_lite()
    con.execute(
        "INSERT INTO alert_log (as_of, pair, z, reason, created_at) VALUES (?,?,?,?,?)",
        ("2026-09-01", "A/B", 2.5, "z", "2026-09-01T12:00:00")
    )
    con.commit()
    
    res = get_alerts(con, "2026-09-01", "2026-09-01")
    assert len(res) == 1
    assert res[0]["pair"] == "A/B"
    con.close()
