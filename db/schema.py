"""
db/schema.py
============
DDL for all DuckDB (analytics) and SQLite (app state) tables.

Each function is idempotent — safe to call on an already-initialised
database.  All CREATE TABLE statements use ``IF NOT EXISTS``.

DuckDB tables (DATABASE.md §2)
-------------------------------
  contract_meta       static contract specifications
  bhav_raw            raw daily settlement data — INSERT-ONLY
  bhav_norm           normalised price per gram at 999 purity
  pair_spread         nearest-expiry pairs with carry adjustment
  bt_run              backtest run metadata and headline metrics
  bt_trade            per-trade fills, costs and PnL
  bt_daily            daily strategy vs gold return series
  contract_calendar   contract lifecycle events

SQLite tables (DATABASE.md §3)
-------------------------------
  users               RBAC user accounts
  login_attempts      brute-force / rate-limit audit
  role_audit          role-change audit trail
  alert_subscription  per-user per-pair alert preferences
  alert_log           triggered alert history
"""

from __future__ import annotations

import sqlite3

import duckdb

# ── DuckDB DDL ────────────────────────────────────────────────────────────────

_DUCKDB_DDL: list[str] = [
    # ── Static contract metadata ─────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS contract_meta (
        symbol          VARCHAR PRIMARY KEY,
        lot_grams       DOUBLE  NOT NULL,   -- trading unit in grams
        quote_grams     DOUBLE  NOT NULL,   -- price is per this many grams
        purity          INTEGER NOT NULL,   -- 995 or 999
        expiry_window   VARCHAR NOT NULL    -- e.g. '3rd-5th' or '27th-31st'
    )
    """,

    # ── Raw daily settlement data — IMMUTABLE after insert ───────────────────
    # DATABASE.md §4: bhav_raw is insert-only.
    # TESTING.md §2: a test must attempt an UPDATE and confirm it fails.
    """
    CREATE TABLE IF NOT EXISTS bhav_raw (
        trade_date      DATE      NOT NULL,
        symbol          VARCHAR   NOT NULL,
        expiry_date     DATE      NOT NULL,
        open            DOUBLE,
        high            DOUBLE,
        low             DOUBLE,
        close           DOUBLE,
        volume          BIGINT,
        open_interest   BIGINT,
        source          VARCHAR   NOT NULL,  -- 'mcx_live' | 'local_file'
        ingested_at     TIMESTAMP NOT NULL,
        PRIMARY KEY (trade_date, symbol, expiry_date)
    )
    """,

    # ── Normalised price per gram at 999 purity ──────────────────────────────
    # Derived from bhav_raw by model/normalize.py (MODEL.md §1).
    """
    CREATE TABLE IF NOT EXISTS bhav_norm (
        trade_date       DATE    NOT NULL,
        symbol           VARCHAR NOT NULL,
        expiry_date      DATE    NOT NULL,
        px_per_gram_999  DOUBLE  NOT NULL,
        days_to_expiry   INTEGER NOT NULL,
        liquidity_bucket VARCHAR,           -- 'thin' | 'ok' | 'deep'
        PRIMARY KEY (trade_date, symbol, expiry_date)
    )
    """,

    # ── Nearest-expiry pairs with carry adjustment ───────────────────────────
    # Produced by model/pairing.py (MODEL.md §2).
    """
    CREATE TABLE IF NOT EXISTS pair_spread (
        trade_date       DATE    NOT NULL,
        leg_a            VARCHAR NOT NULL,
        expiry_a         DATE    NOT NULL,
        leg_b            VARCHAR NOT NULL,
        expiry_b         DATE    NOT NULL,
        expiry_gap_days  INTEGER NOT NULL,  -- signed: expiry_a - expiry_b in days
        raw_spread       DOUBLE  NOT NULL,  -- px_a - px_b per gram
        carry_adj_spread DOUBLE,            -- after expiry-gap carry adjustment
        PRIMARY KEY (trade_date, leg_a, expiry_a, leg_b, expiry_b)
    )
    """,

    # ── Backtest run metadata and headline metrics ────────────────────────────
    # Every run stores snapshot_hash, config_hash and code_version (MODEL.md §12).
    # A run whose code_version ends in '-dirty' must be flagged non-reproducible.
    """
    CREATE TABLE IF NOT EXISTS bt_run (
        run_id          VARCHAR   PRIMARY KEY,
        created_at      TIMESTAMP NOT NULL,
        snapshot_hash   VARCHAR   NOT NULL,  -- sha256:v1:<hex>  (MODEL.md §12.4)
        config_hash     VARCHAR   NOT NULL,  -- sha256:v1:<hex>  (MODEL.md §12.1)
        code_version    VARCHAR   NOT NULL,  -- git SHA, suffix '-dirty' if uncommitted
        config_json     JSON,
        period_start    DATE,
        period_end      DATE,
        holdout_start   DATE,
        gross_pnl       DOUBLE,
        total_cost      DOUBLE,
        net_pnl         DOUBLE,
        max_drawdown    DOUBLE,
        sharpe          DOUBLE,
        beta_gold       DOUBLE,
        alpha_annual    DOUBLE,
        r2_gold         DOUBLE,
        n_trades        INTEGER,
        alert_days      INTEGER,
        total_days      INTEGER
    )
    """,

    # ── Per-trade fills, costs and PnL ────────────────────────────────────────
    # Records the actual (symbol, expiry) held — never a synthetic roll series.
    """
    CREATE TABLE IF NOT EXISTS bt_trade (
        run_id        VARCHAR NOT NULL,
        trade_id      INTEGER NOT NULL,
        leg_a         VARCHAR NOT NULL,
        expiry_a      DATE    NOT NULL,
        leg_b         VARCHAR NOT NULL,
        expiry_b      DATE    NOT NULL,
        entry_date    DATE    NOT NULL,
        exit_date     DATE,
        exit_reason   VARCHAR,             -- 'target' | 'stop' | 'time' | 'calendar'
        qty_a         INTEGER NOT NULL,
        qty_b         INTEGER NOT NULL,
        entry_px_a    DOUBLE,
        entry_px_b    DOUBLE,
        exit_px_a     DOUBLE,
        exit_px_b     DOUBLE,
        gross_pnl     DOUBLE,
        cost          DOUBLE,
        net_pnl       DOUBLE,
        PRIMARY KEY (run_id, trade_id)
    )
    """,

    # ── Daily strategy vs gold return series ─────────────────────────────────
    # Used for gold-beta attribution regression (MODEL.md §8).
    """
    CREATE TABLE IF NOT EXISTS bt_daily (
        run_id              VARCHAR NOT NULL,
        trade_date          DATE    NOT NULL,
        strategy_ret        DOUBLE,
        gold_ret            DOUBLE,
        position_notional   DOUBLE,
        PRIMARY KEY (run_id, trade_date)
    )
    """,

    # ── Contract lifecycle calendar ───────────────────────────────────────────
    # Drives signal calendar filters (MODEL.md §4 liquidity / tender checks).
    """
    CREATE TABLE IF NOT EXISTS contract_calendar (
        symbol            VARCHAR NOT NULL,
        expiry_date       DATE    NOT NULL,
        listing_date      DATE,
        first_liquid_date DATE,
        tender_start      DATE,
        last_trade_date   DATE,
        PRIMARY KEY (symbol, expiry_date)
    )
    """,

    # ── Indexes (DATABASE.md §4) ──────────────────────────────────────────────
    "CREATE INDEX IF NOT EXISTS idx_bhav_raw_date    ON bhav_raw  (trade_date)",
    "CREATE INDEX IF NOT EXISTS idx_bhav_raw_sym_exp ON bhav_raw  (symbol, expiry_date, trade_date)",
    "CREATE INDEX IF NOT EXISTS idx_bhav_norm_date   ON bhav_norm (trade_date)",
    "CREATE INDEX IF NOT EXISTS idx_pair_date        ON pair_spread (trade_date)",
    "CREATE INDEX IF NOT EXISTS idx_bt_trade_run     ON bt_trade  (run_id)",
    "CREATE INDEX IF NOT EXISTS idx_bt_daily_run     ON bt_daily  (run_id)",
]

# ── SQLite DDL ────────────────────────────────────────────────────────────────

_SQLITE_DDL: list[str] = [
    # ── User accounts ─────────────────────────────────────────────────────────
    # password_hash: argon2id, parameters pinned in AUTH.md §2.1.
    # Never returned by the API.
    """
    CREATE TABLE IF NOT EXISTS users (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        username      TEXT    UNIQUE NOT NULL,
        password_hash TEXT    NOT NULL,
        role          TEXT    NOT NULL DEFAULT 'viewer',
        created_at    TEXT    NOT NULL
    )
    """,

    # ── Login attempt audit (rate-limit source of truth) ─────────────────────
    """
    CREATE TABLE IF NOT EXISTS login_attempts (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        username     TEXT    NOT NULL,
        ip           TEXT,
        attempted_at TEXT    NOT NULL,
        success      INTEGER NOT NULL    -- 1 = success, 0 = failure
    )
    """,

    # ── Role-change audit trail ───────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS role_audit (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER NOT NULL,
        changed_by  INTEGER NOT NULL,
        old_role    TEXT    NOT NULL,
        new_role    TEXT    NOT NULL,
        changed_at  TEXT    NOT NULL
    )
    """,

    # ── Per-user alert preferences ────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS alert_subscription (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id         INTEGER NOT NULL,
        pair            TEXT    NOT NULL,   -- e.g. 'GOLDM/GOLDPETAL'
        z_threshold     REAL    NOT NULL,
        min_liquidity   TEXT    NOT NULL DEFAULT 'ok'
    )
    """,

    # ── Triggered alert history ───────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS alert_log (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        as_of       TEXT    NOT NULL,       -- ISO date string
        pair        TEXT    NOT NULL,
        z           REAL    NOT NULL,
        reason      TEXT,
        created_at  TEXT    NOT NULL
    )
    """,

    # ── Background Jobs ───────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS background_jobs (
        job_id      TEXT PRIMARY KEY,
        job_type    TEXT NOT NULL,    -- 'ingest' | 'backtest'
        status      TEXT NOT NULL,    -- 'pending' | 'running' | 'completed' | 'failed'
        progress    TEXT,             -- json or string log
        error       TEXT,
        created_at  TEXT NOT NULL,
        updated_at  TEXT NOT NULL
    )
    """,

    # ── Indexes ───────────────────────────────────────────────────────────────
    "CREATE INDEX IF NOT EXISTS idx_login_username ON login_attempts (username)",
    "CREATE INDEX IF NOT EXISTS idx_login_ip       ON login_attempts (ip)",
    "CREATE INDEX IF NOT EXISTS idx_alert_log_date ON alert_log (as_of)",
    "CREATE INDEX IF NOT EXISTS idx_jobs_status    ON background_jobs (status)",
]


# ── Public helpers ────────────────────────────────────────────────────────────

def create_analytics_schema(con: duckdb.DuckDBPyConnection) -> None:
    """Apply all DuckDB DDL statements to *con*.

    Idempotent — uses ``CREATE TABLE IF NOT EXISTS`` throughout.

    Args:
        con: An open DuckDB connection (persistent or in-memory).
    """
    for stmt in _DUCKDB_DDL:
        con.execute(stmt)


def create_app_schema(con: sqlite3.Connection) -> None:
    """Apply all SQLite DDL statements to *con*.

    Idempotent — uses ``CREATE TABLE IF NOT EXISTS`` throughout.

    Args:
        con: An open SQLite connection.
    """
    for stmt in _SQLITE_DDL:
        con.execute(stmt)
    con.commit()
