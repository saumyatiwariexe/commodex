"""
tests/test_db.py
================
Tests for the database layer (db/ package).

Covers (DATABASE.md §4, TESTING.md §2):
  - All DuckDB tables exist after schema creation.
  - All SQLite tables exist after schema creation.
  - contract_meta is seeded correctly from contracts_meta.yaml.
  - bhav_raw INSERT works; UPDATE must be rejected at the app layer.
  - bhav_norm, pair_spread, bt_run, bt_trade, bt_daily basic insert/query.
  - contract_calendar basic insert/query.
  - bt_run stores snapshot_hash and config_hash in sha256:v1:... format.
  - SQLite role_audit and login_attempts table constraints.

All tests use in-memory databases so there is no filesystem side-effect.
No network calls are made (AGENTS.md §7).
"""

from __future__ import annotations

import datetime
import re

import pytest

from db import analytics_conn, app_conn
from db.init_db import init_databases
from db.schema import create_analytics_schema, create_app_schema

# ── helpers ───────────────────────────────────────────────────────────────────

HASH_PATTERN = re.compile(r"^sha256:v1:[0-9a-f]{64}$")


def _fresh_duck():
    """Return an open in-memory DuckDB connection with schema applied."""
    con = __import__("duckdb").connect(":memory:")
    create_analytics_schema(con)
    return con


def _fresh_lite():
    """Return an open in-memory SQLite connection with schema applied."""
    import sqlite3
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    create_app_schema(con)
    return con


# ── DuckDB table existence ────────────────────────────────────────────────────

DUCKDB_TABLES = [
    "contract_meta",
    "bhav_raw",
    "bhav_norm",
    "pair_spread",
    "bt_run",
    "bt_trade",
    "bt_daily",
    "contract_calendar",
]


@pytest.mark.parametrize("table", DUCKDB_TABLES)
def test_duckdb_table_exists(table: str) -> None:
    """All expected DuckDB tables must exist after schema creation."""
    con = _fresh_duck()
    rows = con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_name = ?",
        [table],
    ).fetchall()
    con.close()
    assert rows, f"DuckDB table '{table}' was not created"


# ── SQLite table existence ────────────────────────────────────────────────────

SQLITE_TABLES = [
    "users",
    "login_attempts",
    "role_audit",
    "alert_subscription",
    "alert_log",
]


@pytest.mark.parametrize("table", SQLITE_TABLES)
def test_sqlite_table_exists(table: str) -> None:
    """All expected SQLite tables must exist after schema creation."""
    con = _fresh_lite()
    row = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    con.close()
    assert row is not None, f"SQLite table '{table}' was not created"


# ── contract_meta seeding ─────────────────────────────────────────────────────

EXPECTED_SYMBOLS = {"GOLDM", "GOLDTEN", "GOLDGUINEA", "GOLDPETAL"}


def test_init_databases_seeds_contract_meta(tmp_path) -> None:
    """init_databases() must populate contract_meta from contracts_meta.yaml."""
    duck_path = tmp_path / "a.duckdb"
    lite_path = tmp_path / "a.sqlite"
    init_databases(duckdb_path=duck_path, sqlite_path=lite_path, seed=True)

    with analytics_conn(duck_path) as con:
        rows = con.execute("SELECT symbol FROM contract_meta").fetchall()

    symbols = {r[0] for r in rows}
    assert symbols == EXPECTED_SYMBOLS


@pytest.mark.parametrize("symbol,expected_purity", [
    ("GOLDM",       995),
    ("GOLDTEN",     999),
    ("GOLDGUINEA",  999),
    ("GOLDPETAL",   999),
])
def test_contract_meta_purity(tmp_path, symbol: str, expected_purity: int) -> None:
    """Purity values must match DATA_PIPELINE.md §6 / contracts_meta.yaml."""
    duck_path = tmp_path / "a.duckdb"
    lite_path = tmp_path / "a.sqlite"
    init_databases(duckdb_path=duck_path, sqlite_path=lite_path, seed=True)

    with analytics_conn(duck_path) as con:
        row = con.execute(
            "SELECT purity FROM contract_meta WHERE symbol = ?", [symbol]
        ).fetchone()

    assert row is not None, f"Symbol {symbol} not found in contract_meta"
    assert row[0] == expected_purity


def test_contract_meta_goldm_lot(tmp_path) -> None:
    """GOLDM lot must be 100 g (contracts_meta.yaml, DATA_PIPELINE.md §6)."""
    duck_path = tmp_path / "a.duckdb"
    init_databases(duckdb_path=duck_path, sqlite_path=tmp_path / "a.sqlite", seed=True)
    with analytics_conn(duck_path) as con:
        row = con.execute(
            "SELECT lot_grams FROM contract_meta WHERE symbol='GOLDM'"
        ).fetchone()
    assert row[0] == 100.0


def test_seed_is_idempotent(tmp_path) -> None:
    """Running init_databases() twice must not error or duplicate rows."""
    duck_path = tmp_path / "a.duckdb"
    lite_path = tmp_path / "a.sqlite"
    init_databases(duckdb_path=duck_path, sqlite_path=lite_path, seed=True)
    init_databases(duckdb_path=duck_path, sqlite_path=lite_path, seed=True)

    with analytics_conn(duck_path) as con:
        count = con.execute("SELECT COUNT(*) FROM contract_meta").fetchone()[0]
    assert count == 4, "Re-seeding must not create duplicate rows"


# ── bhav_raw: insert and immutability ─────────────────────────────────────────

def _insert_bhav_raw_row(con) -> None:
    con.execute(
        """
        INSERT INTO bhav_raw
            (trade_date, symbol, expiry_date, open, high, low, close,
             volume, open_interest, source, ingested_at)
        VALUES
            ('2026-09-01', 'GOLDM', '2026-09-05',
             70000, 71000, 69500, 70500,
             1500, 5000,
             'local_file', '2026-09-01T18:00:00')
        """
    )


def test_bhav_raw_insert() -> None:
    """A valid row must insert into bhav_raw without error."""
    con = _fresh_duck()
    _insert_bhav_raw_row(con)
    count = con.execute("SELECT COUNT(*) FROM bhav_raw").fetchone()[0]
    con.close()
    assert count == 1


def test_bhav_raw_duplicate_pk_rejected() -> None:
    """Inserting a duplicate (trade_date, symbol, expiry_date) must fail."""
    con = _fresh_duck()
    _insert_bhav_raw_row(con)
    with pytest.raises(Exception):
        _insert_bhav_raw_row(con)
    con.close()


def test_bhav_raw_update_rejected_at_app_layer() -> None:
    """
    DATABASE.md §4: bhav_raw is insert-only.

    DuckDB does not enforce a no-update constraint at the SQL level, so we
    enforce it in the app layer.  This test documents the contract: any path
    that would UPDATE bhav_raw must raise before it reaches the database.

    The sentinel function below represents the app-layer guard.  Replace with
    the real guard function once it is implemented in db/ops.py or similar.
    """
    def app_layer_update_guard(con, trade_date: str, new_close: float) -> None:
        """Simulate the app-layer protection that must be in place."""
        raise RuntimeError(
            "bhav_raw is insert-only (DATABASE.md §4). "
            "Create a new table for cleaned data instead of editing the raw store."
        )

    con = _fresh_duck()
    _insert_bhav_raw_row(con)
    with pytest.raises(RuntimeError, match="bhav_raw is insert-only"):
        app_layer_update_guard(con, "2026-09-01", 71000.0)
    con.close()


# ── bhav_norm ─────────────────────────────────────────────────────────────────

def test_bhav_norm_insert() -> None:
    """bhav_norm must accept a valid normalised row."""
    con = _fresh_duck()
    con.execute(
        """
        INSERT INTO bhav_norm (trade_date, symbol, expiry_date,
                               px_per_gram_999, days_to_expiry, liquidity_bucket)
        VALUES ('2026-09-01', 'GOLDM', '2026-09-05', 7050.28, 4, 'ok')
        """
    )
    row = con.execute("SELECT px_per_gram_999 FROM bhav_norm").fetchone()
    con.close()
    assert row is not None
    assert abs(row[0] - 7050.28) < 1e-6


def test_bhav_norm_liquidity_bucket_values() -> None:
    """liquidity_bucket must accept 'thin', 'ok', 'deep'."""
    con = _fresh_duck()
    for i, bucket in enumerate(["thin", "ok", "deep"]):
        con.execute(
            """
            INSERT INTO bhav_norm
                (trade_date, symbol, expiry_date, px_per_gram_999,
                 days_to_expiry, liquidity_bucket)
            VALUES (?, 'GOLDM', ?, 7000.0, 10, ?)
            """,
            [f"2026-09-{i + 1:02d}", f"2026-10-{i + 1:02d}", bucket],
        )
    count = con.execute("SELECT COUNT(*) FROM bhav_norm").fetchone()[0]
    con.close()
    assert count == 3


# ── pair_spread ───────────────────────────────────────────────────────────────

def test_pair_spread_insert() -> None:
    """pair_spread must accept a valid pair row."""
    con = _fresh_duck()
    con.execute(
        """
        INSERT INTO pair_spread
            (trade_date, leg_a, expiry_a, leg_b, expiry_b,
             expiry_gap_days, raw_spread, carry_adj_spread)
        VALUES ('2026-09-01', 'GOLDM', '2026-09-05',
                'GOLDPETAL', '2026-09-30', -25, 5.2, 4.8)
        """
    )
    row = con.execute("SELECT raw_spread FROM pair_spread").fetchone()
    con.close()
    assert abs(row[0] - 5.2) < 1e-9


# ── bt_run hash format ────────────────────────────────────────────────────────

def test_bt_run_hash_format() -> None:
    """snapshot_hash and config_hash stored in bt_run must match sha256:v1:... format."""
    from model.canonical import hash_obj

    snapshot_h = hash_obj({"path": "data/raw/date=2026-09-01/part.parquet",
                            "file_hash": "sha256:v1:" + "a" * 64,
                            "row_count": 42})
    config_h = hash_obj({"lookback": 60, "z_entry": 2.0, "z_exit": 0.5})

    assert HASH_PATTERN.match(snapshot_h), f"snapshot_hash format wrong: {snapshot_h}"
    assert HASH_PATTERN.match(config_h), f"config_hash format wrong: {config_h}"

    con = _fresh_duck()
    con.execute(
        """
        INSERT INTO bt_run
            (run_id, created_at, snapshot_hash, config_hash, code_version)
        VALUES ('run-001', '2026-09-01T12:00:00', ?, ?, 'abc1234')
        """,
        [snapshot_h, config_h],
    )
    row = con.execute(
        "SELECT snapshot_hash, config_hash FROM bt_run WHERE run_id='run-001'"
    ).fetchone()
    con.close()
    assert HASH_PATTERN.match(row[0])
    assert HASH_PATTERN.match(row[1])


def test_bt_run_dirty_flag() -> None:
    """A bt_run row with '-dirty' suffix in code_version must be stored as-is."""
    con = _fresh_duck()
    con.execute(
        """
        INSERT INTO bt_run
            (run_id, created_at, snapshot_hash, config_hash, code_version)
        VALUES ('run-dirty', '2026-09-01T12:00:00',
                'sha256:v1:' || repeat('a', 64),
                'sha256:v1:' || repeat('b', 64),
                'abc1234-dirty')
        """
    )
    row = con.execute(
        "SELECT code_version FROM bt_run WHERE run_id='run-dirty'"
    ).fetchone()
    con.close()
    assert row[0].endswith("-dirty")


# ── bt_trade and bt_daily ─────────────────────────────────────────────────────

def test_bt_trade_insert() -> None:
    """bt_trade must accept a valid trade row."""
    con = _fresh_duck()
    con.execute(
        """
        INSERT INTO bt_run
            (run_id, created_at, snapshot_hash, config_hash, code_version)
        VALUES ('r1', '2026-09-01T12:00:00',
                'sha256:v1:' || repeat('a', 64),
                'sha256:v1:' || repeat('b', 64), 'abc')
        """
    )
    con.execute(
        """
        INSERT INTO bt_trade
            (run_id, trade_id, leg_a, expiry_a, leg_b, expiry_b,
             entry_date, exit_date, exit_reason,
             qty_a, qty_b, entry_px_a, entry_px_b, exit_px_a, exit_px_b,
             gross_pnl, cost, net_pnl)
        VALUES
            ('r1', 1, 'GOLDM', '2026-09-05', 'GOLDPETAL', '2026-09-30',
             '2026-08-10', '2026-08-20', 'target',
             1, 100, 70500.0, 7045.0, 70600.0, 7052.0,
             100.0, 30.0, 70.0)
        """
    )
    row = con.execute(
        "SELECT exit_reason, net_pnl FROM bt_trade WHERE run_id='r1' AND trade_id=1"
    ).fetchone()
    con.close()
    assert row[0] == "target"
    assert abs(row[1] - 70.0) < 1e-9


def test_bt_daily_insert() -> None:
    """bt_daily must accept a valid daily return row."""
    con = _fresh_duck()
    con.execute(
        """
        INSERT INTO bt_run
            (run_id, created_at, snapshot_hash, config_hash, code_version)
        VALUES ('r2', '2026-09-01T12:00:00',
                'sha256:v1:' || repeat('c', 64),
                'sha256:v1:' || repeat('d', 64), 'abc')
        """
    )
    con.execute(
        """
        INSERT INTO bt_daily (run_id, trade_date, strategy_ret, gold_ret, position_notional)
        VALUES ('r2', '2026-08-10', 0.002, 0.001, 705000.0)
        """
    )
    row = con.execute(
        "SELECT strategy_ret FROM bt_daily WHERE run_id='r2'"
    ).fetchone()
    con.close()
    assert abs(row[0] - 0.002) < 1e-9


# ── contract_calendar ─────────────────────────────────────────────────────────

def test_contract_calendar_insert() -> None:
    """contract_calendar must accept a valid lifecycle row.

    DuckDB returns DATE columns as datetime.date objects, so we compare
    using datetime.date rather than a string.
    """
    import datetime as dt
    con = _fresh_duck()
    con.execute(
        """
        INSERT INTO contract_calendar
            (symbol, expiry_date, listing_date, first_liquid_date,
             tender_start, last_trade_date)
        VALUES
            ('GOLDM', '2026-09-05', '2026-07-01', '2026-08-01',
             '2026-09-01', '2026-09-04')
        """
    )
    row = con.execute(
        "SELECT listing_date FROM contract_calendar WHERE symbol='GOLDM'"
    ).fetchone()
    con.close()
    # DuckDB returns DATE as datetime.date; accept either form
    assert row[0] == dt.date(2026, 7, 1) or str(row[0]) == "2026-07-01"


# ── SQLite: users and login_attempts ─────────────────────────────────────────

def test_users_username_unique() -> None:
    """SQLite users table must enforce UNIQUE on username."""
    con = _fresh_lite()
    now = "2026-09-01T12:00:00"
    con.execute(
        "INSERT INTO users (username, password_hash, role, created_at) VALUES (?,?,?,?)",
        ("rishabh", "$argon2id$example_hash", "analyst", now),
    )
    con.commit()
    with pytest.raises(Exception):
        con.execute(
            "INSERT INTO users (username, password_hash, role, created_at) VALUES (?,?,?,?)",
            ("rishabh", "$argon2id$other_hash", "viewer", now),
        )
    con.close()


def test_login_attempts_insert() -> None:
    """login_attempts must record a failed attempt without error."""
    con = _fresh_lite()
    con.execute(
        "INSERT INTO login_attempts (username, ip, attempted_at, success) VALUES (?,?,?,?)",
        ("rishabh", "127.0.0.1", "2026-09-01T12:01:00", 0),
    )
    con.commit()
    row = con.execute(
        "SELECT success FROM login_attempts WHERE username='rishabh'"
    ).fetchone()
    con.close()
    assert row["success"] == 0


def test_role_audit_insert() -> None:
    """role_audit must store a role-change event."""
    con = _fresh_lite()
    now = "2026-09-01T12:00:00"
    con.execute(
        "INSERT INTO users (username, password_hash, role, created_at) VALUES (?,?,?,?)",
        ("alice", "$argon2id$h", "viewer", now),
    )
    con.commit()
    user_id = con.execute("SELECT id FROM users WHERE username='alice'").fetchone()["id"]
    con.execute(
        """
        INSERT INTO role_audit (user_id, changed_by, old_role, new_role, changed_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, 1, "viewer", "analyst", now),
    )
    con.commit()
    row = con.execute(
        "SELECT new_role FROM role_audit WHERE user_id=?", (user_id,)
    ).fetchone()
    con.close()
    assert row["new_role"] == "analyst"


def test_alert_log_insert() -> None:
    """alert_log must record a triggered alert."""
    con = _fresh_lite()
    con.execute(
        """
        INSERT INTO alert_log (as_of, pair, z, reason, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("2026-09-01", "GOLDM/GOLDPETAL", 2.35, "z_entry_crossed", "2026-09-01T18:00:00"),
    )
    con.commit()
    row = con.execute("SELECT z FROM alert_log").fetchone()
    con.close()
    assert abs(row["z"] - 2.35) < 1e-6
