"""
db/ops.py
=========
Write operations that persist model outputs into DuckDB and SQLite.

This module is the handoff boundary between the model layer (pure functions,
no I/O) and the database layer.  All functions here:
  - Accept typed model outputs (DataFrames, dataclasses, plain dicts).
  - Write to the correct table(s) via parameterised queries.
  - Enforce the integrity rules from DATABASE.md §4.

Public API
----------
  write_bhav_raw(con, df)          → insert rows into bhav_raw (insert-only)
  write_bhav_norm(con, df)         → upsert rows into bhav_norm
  write_pair_spread(con, df)       → upsert rows into pair_spread
  write_bt_run(con, run)           → insert a bt_run summary row
  write_bt_trades(con, run_id, df) → insert bt_trade rows for a run
  write_bt_daily(con, run_id, df)  → insert bt_daily rows for a run
  write_contract_calendar(con, df) → upsert contract_calendar rows

Rules (DATABASE.md §4, AGENTS.md §7, §8)
-----------------------------------------
  - bhav_raw is INSERT-ONLY.  This module never issues UPDATE/DELETE on it.
  - All DML uses parameterised queries.  No string-built SQL anywhere.
  - Hashes written to bt_run must be in the sha256:v1:<hex> format
    (MODEL.md §12).  Validated before write.
  - NaN carry_adj_spread values are written as NULL (SQL-safe float).
"""

from __future__ import annotations

import datetime
import logging
import math
import re
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

_HASH_RE = re.compile(r"^sha256:v\d+:[0-9a-f]{64}$")

# ── internal helpers ──────────────────────────────────────────────────────────

def _nan_to_none(v: Any) -> Any:
    """Convert float NaN to None (SQL NULL). Leaves all other values unchanged."""
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def _validate_hash(h: str, name: str) -> None:
    """Raise ValueError if *h* does not match the sha256:vN:<hex> format."""
    if not _HASH_RE.match(h):
        raise ValueError(
            f"ops.write_bt_run: {name} must match sha256:vN:<64 hex chars>, "
            f"got: {h!r}"
        )


# ── bhav_raw (INSERT-ONLY) ────────────────────────────────────────────────────

def write_bhav_raw(con, df: pd.DataFrame) -> int:
    """Insert new rows into bhav_raw.  bhav_raw is INSERT-ONLY (DATABASE.md §4).

    Existing rows (same primary key) are skipped silently with
    ``ON CONFLICT DO NOTHING`` — re-ingesting the same date is a no-op
    (DATA_PIPELINE.md §5).

    Parameters
    ----------
    con:
        Open DuckDB connection (from ``db.analytics_conn``).
    df:
        DataFrame with columns matching bhav_raw:
        ``trade_date``, ``symbol``, ``expiry_date``, ``open``, ``high``,
        ``low``, ``close``, ``volume``, ``open_interest``, ``source``,
        ``ingested_at``.

    Returns
    -------
    Number of rows actually inserted (duplicates excluded).
    """
    required = {
        "trade_date", "symbol", "expiry_date",
        "open", "high", "low", "close",
        "volume", "open_interest", "source", "ingested_at",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"write_bhav_raw: missing columns: {sorted(missing)}")

    if df.empty:
        logger.debug("write_bhav_raw: empty DataFrame, nothing to insert")
        return 0

    rows_before = con.execute("SELECT COUNT(*) FROM bhav_raw").fetchone()[0]

    for _, row in df.iterrows():
        con.execute(
            """
            INSERT INTO bhav_raw
                (trade_date, symbol, expiry_date,
                 open, high, low, close,
                 volume, open_interest, source, ingested_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT DO NOTHING
            """,
            [
                row["trade_date"], str(row["symbol"]).strip(),
                row["expiry_date"],
                _nan_to_none(row.get("open")),
                _nan_to_none(row.get("high")),
                _nan_to_none(row.get("low")),
                _nan_to_none(row.get("close")),
                None if pd.isna(row.get("volume")) else int(row["volume"]),
                None if pd.isna(row.get("open_interest")) else int(row["open_interest"]),
                str(row["source"]),
                row["ingested_at"],
            ],
        )

    rows_after = con.execute("SELECT COUNT(*) FROM bhav_raw").fetchone()[0]
    inserted = rows_after - rows_before
    logger.info("write_bhav_raw: inserted %d / %d rows", inserted, len(df))
    return inserted


# ── bhav_norm ─────────────────────────────────────────────────────────────────

def write_bhav_norm(con, df: pd.DataFrame) -> int:
    """Upsert rows into bhav_norm (normalized INR/gram at 999 purity).

    ``ON CONFLICT DO UPDATE`` — re-processing the same (date, symbol, expiry)
    replaces the normalised value (safe because bhav_raw is immutable and
    normalization is deterministic).

    Parameters
    ----------
    con:
        Open DuckDB connection.
    df:
        DataFrame with columns: ``trade_date``, ``symbol``, ``expiry_date``,
        ``px_per_gram_999``, ``days_to_expiry``.
        Optional: ``liquidity_bucket`` (defaults to NULL).

    Returns
    -------
    Number of rows in the DataFrame (all processed).
    """
    required = {"trade_date", "symbol", "expiry_date", "px_per_gram_999", "days_to_expiry"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"write_bhav_norm: missing columns: {sorted(missing)}")

    if df.empty:
        return 0

    for _, row in df.iterrows():
        bucket = row.get("liquidity_bucket", None)
        con.execute(
            """
            INSERT INTO bhav_norm
                (trade_date, symbol, expiry_date,
                 px_per_gram_999, days_to_expiry, liquidity_bucket)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (trade_date, symbol, expiry_date) DO UPDATE SET
                px_per_gram_999  = excluded.px_per_gram_999,
                days_to_expiry   = excluded.days_to_expiry,
                liquidity_bucket = excluded.liquidity_bucket
            """,
            [
                row["trade_date"], str(row["symbol"]).strip(),
                row["expiry_date"],
                float(row["px_per_gram_999"]),
                int(row["days_to_expiry"]),
                None if (bucket is None or (isinstance(bucket, float) and math.isnan(bucket)))
                     else str(bucket),
            ],
        )

    logger.info("write_bhav_norm: upserted %d rows", len(df))
    return len(df)


# ── pair_spread ───────────────────────────────────────────────────────────────

def write_pair_spread(con, df: pd.DataFrame) -> int:
    """Upsert rows into pair_spread.

    ``carry_adj_spread`` may be NaN (when carry estimation failed for a date);
    it is written as NULL.

    Parameters
    ----------
    con:
        Open DuckDB connection.
    df:
        DataFrame matching the output of ``model.pairing.build_pairs_df``.
        Required columns: ``trade_date``, ``symbol_a``, ``expiry_a``,
        ``symbol_b``, ``expiry_b``, ``expiry_gap_days``, ``raw_spread``.
        Optional: ``carry_adj_spread``.

    Returns
    -------
    Number of rows in the DataFrame (all processed).
    """
    required = {
        "trade_date", "symbol_a", "expiry_a",
        "symbol_b", "expiry_b", "expiry_gap_days", "raw_spread",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"write_pair_spread: missing columns: {sorted(missing)}")

    if df.empty:
        return 0

    for _, row in df.iterrows():
        con.execute(
            """
            INSERT INTO pair_spread
                (trade_date, leg_a, expiry_a, leg_b, expiry_b,
                 expiry_gap_days, raw_spread, carry_adj_spread)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (trade_date, leg_a, expiry_a, leg_b, expiry_b) DO UPDATE SET
                expiry_gap_days  = excluded.expiry_gap_days,
                raw_spread       = excluded.raw_spread,
                carry_adj_spread = excluded.carry_adj_spread
            """,
            [
                row["trade_date"],
                str(row["symbol_a"]).strip(), row["expiry_a"],
                str(row["symbol_b"]).strip(), row["expiry_b"],
                int(row["expiry_gap_days"]),
                float(row["raw_spread"]),
                _nan_to_none(row.get("carry_adj_spread")),
            ],
        )

    logger.info("write_pair_spread: upserted %d rows", len(df))
    return len(df)


# ── bt_run ────────────────────────────────────────────────────────────────────

def write_bt_run(con, run: dict[str, Any]) -> None:
    """Insert one backtest run summary row into bt_run.

    The three reproducibility fields — ``snapshot_hash``, ``config_hash``,
    ``code_version`` — are required and validated (MODEL.md §12).

    Parameters
    ----------
    con:
        Open DuckDB connection.
    run:
        Dict with at minimum: ``run_id``, ``created_at``, ``snapshot_hash``,
        ``config_hash``, ``code_version``.
        All other fields are optional; missing metric fields default to None.

    Raises
    ------
    ValueError
        If ``run_id``, ``snapshot_hash``, ``config_hash``, or ``code_version``
        are missing, or if either hash is in the wrong format.
    """
    for key in ("run_id", "snapshot_hash", "config_hash", "code_version"):
        if not run.get(key):
            raise ValueError(f"write_bt_run: required field {key!r} is missing or empty")

    _validate_hash(run["snapshot_hash"], "snapshot_hash")
    _validate_hash(run["config_hash"], "config_hash")

    created_at = run.get("created_at") or datetime.datetime.now(tz=datetime.timezone.utc).isoformat()

    con.execute(
        """
        INSERT INTO bt_run (
            run_id, created_at,
            snapshot_hash, config_hash, code_version, config_json,
            period_start, period_end, holdout_start,
            gross_pnl, total_cost, net_pnl,
            max_drawdown, sharpe,
            beta_gold, alpha_annual, r2_gold,
            n_trades, alert_days, total_days
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            run["run_id"], created_at,
            run["snapshot_hash"], run["config_hash"],
            run["code_version"],
            run.get("config_json"),
            run.get("period_start"), run.get("period_end"),
            run.get("holdout_start"),
            _nan_to_none(run.get("gross_pnl")),
            _nan_to_none(run.get("total_cost")),
            _nan_to_none(run.get("net_pnl")),
            _nan_to_none(run.get("max_drawdown")),
            _nan_to_none(run.get("sharpe")),
            _nan_to_none(run.get("beta_gold")),
            _nan_to_none(run.get("alpha_annual")),
            _nan_to_none(run.get("r2_gold")),
            run.get("n_trades"), run.get("alert_days"), run.get("total_days"),
        ],
    )
    logger.info("write_bt_run: inserted run_id=%s code_version=%s",
                run["run_id"], run["code_version"])


# ── bt_trade ──────────────────────────────────────────────────────────────────

def write_bt_trades(con, run_id: str, df: pd.DataFrame) -> int:
    """Insert trade rows for a backtest run into bt_trade.

    Parameters
    ----------
    con:
        Open DuckDB connection.
    run_id:
        Must match an existing bt_run.run_id.
    df:
        DataFrame with one row per trade.  Required columns: ``trade_id``,
        ``leg_a``, ``expiry_a``, ``leg_b``, ``expiry_b``, ``entry_date``,
        ``qty_a``, ``qty_b``.
        Optional: ``exit_date``, ``exit_reason``, ``entry_px_a``,
        ``entry_px_b``, ``exit_px_a``, ``exit_px_b``,
        ``gross_pnl``, ``cost``, ``net_pnl``.

    Returns
    -------
    Number of rows inserted.
    """
    if df.empty:
        return 0

    required = {"trade_id", "leg_a", "expiry_a", "leg_b", "expiry_b", "entry_date", "qty_a", "qty_b"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"write_bt_trades: missing columns: {sorted(missing)}")

    for _, row in df.iterrows():
        con.execute(
            """
            INSERT INTO bt_trade (
                run_id, trade_id,
                leg_a, expiry_a, leg_b, expiry_b,
                entry_date, exit_date, exit_reason,
                qty_a, qty_b,
                entry_px_a, entry_px_b, exit_px_a, exit_px_b,
                gross_pnl, cost, net_pnl
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                run_id, int(row["trade_id"]),
                str(row["leg_a"]).strip(), row["expiry_a"],
                str(row["leg_b"]).strip(), row["expiry_b"],
                row["entry_date"],
                row.get("exit_date"),
                row.get("exit_reason"),
                int(row["qty_a"]), int(row["qty_b"]),
                _nan_to_none(row.get("entry_px_a")),
                _nan_to_none(row.get("entry_px_b")),
                _nan_to_none(row.get("exit_px_a")),
                _nan_to_none(row.get("exit_px_b")),
                _nan_to_none(row.get("gross_pnl")),
                _nan_to_none(row.get("cost")),
                _nan_to_none(row.get("net_pnl")),
            ],
        )

    logger.info("write_bt_trades: inserted %d trades for run_id=%s", len(df), run_id)
    return len(df)


# ── bt_daily ──────────────────────────────────────────────────────────────────

def write_bt_daily(con, run_id: str, df: pd.DataFrame) -> int:
    """Insert daily return series for a backtest run into bt_daily.

    Parameters
    ----------
    con:
        Open DuckDB connection.
    run_id:
        Must match an existing bt_run.run_id.
    df:
        DataFrame with columns: ``trade_date``, ``strategy_ret``,
        ``gold_ret``, ``position_notional``.

    Returns
    -------
    Number of rows inserted.
    """
    if df.empty:
        return 0

    required = {"trade_date", "strategy_ret", "gold_ret"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"write_bt_daily: missing columns: {sorted(missing)}")

    for _, row in df.iterrows():
        con.execute(
            """
            INSERT INTO bt_daily (run_id, trade_date, strategy_ret, gold_ret, position_notional)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                run_id,
                row["trade_date"],
                _nan_to_none(row["strategy_ret"]),
                _nan_to_none(row["gold_ret"]),
                _nan_to_none(row.get("position_notional")),
            ],
        )

    logger.info("write_bt_daily: inserted %d daily rows for run_id=%s", len(df), run_id)
    return len(df)


# ── contract_calendar ─────────────────────────────────────────────────────────

def write_contract_calendar(con, df: pd.DataFrame) -> int:
    """Upsert contract lifecycle events into contract_calendar.

    Parameters
    ----------
    con:
        Open DuckDB connection.
    df:
        DataFrame with columns: ``symbol``, ``expiry_date``.
        Optional: ``listing_date``, ``first_liquid_date``,
        ``tender_start``, ``last_trade_date``.

    Returns
    -------
    Number of rows processed.
    """
    if df.empty:
        return 0

    required = {"symbol", "expiry_date"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"write_contract_calendar: missing columns: {sorted(missing)}")

    for _, row in df.iterrows():
        con.execute(
            """
            INSERT INTO contract_calendar
                (symbol, expiry_date, listing_date, first_liquid_date,
                 tender_start, last_trade_date)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (symbol, expiry_date) DO UPDATE SET
                listing_date      = excluded.listing_date,
                first_liquid_date = excluded.first_liquid_date,
                tender_start      = excluded.tender_start,
                last_trade_date   = excluded.last_trade_date
            """,
            [
                str(row["symbol"]).strip(), row["expiry_date"],
                row.get("listing_date"),
                row.get("first_liquid_date"),
                row.get("tender_start"),
                row.get("last_trade_date"),
            ],
        )

    logger.info("write_contract_calendar: upserted %d rows", len(df))
    return len(df)
