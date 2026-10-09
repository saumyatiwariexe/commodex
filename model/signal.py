"""
model/signal.py
===============
Rolling z-score signal engine (MODEL.md §4).

Algorithm (per pair, per day):
  1. s_t = carry_adj_spread_t
  2. Rolling mean and std over lookback L using data up to and including t
     (no future data — window is expanding from the start, then fixed at L).
  3. z_t = (s_t - mean) / std
  4. Candidate signal if |z_t| >= z_entry AND all filters pass:
       - liquidity bucket of BOTH legs not 'thin'
       - both contracts outside tender period (days_to_expiry > tender_days)
       - both contracts outside last N days before expiry (days_to_expiry > exit_days_before_expiry)
       - expiry_gap_days within [min_gap, max_gap]
  5. Direction: +1 = long A / short B (A cheap), -1 = long B / short A (A rich)
  6. Position exits when:
       - |z| < z_exit      (mean-reversion)
       - z crosses z_stop  (stop-loss, same sign as entry — breach on the wrong side)
       - holding days >= max_hold_days
       - calendar exit: days_to_expiry of either leg <= exit_days_before_expiry

Public API
----------
  LiquidityBucket         enum: LIQUID, NORMAL, THIN
  classify_liquidity()    label each row with a bucket
  compute_zscore_series() compute rolling z-scores for a spread series
  SignalConfig            dataclass for all thresholds (loaded from YAML)
  generate_signals()      main function: pairs_df → signals_df with z, direction, state
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── liquidity ─────────────────────────────────────────────────────────────────

class LiquidityBucket(str, Enum):
    LIQUID = "liquid"
    NORMAL = "normal"
    THIN   = "thin"


def classify_liquidity(
    volume: pd.Series,
    open_interest: pd.Series,
    *,
    vol_thin_pct: float = 20.0,
    vol_liquid_pct: float = 60.0,
    oi_thin_pct: float = 20.0,
    oi_liquid_pct: float = 60.0,
) -> pd.Series:
    """Assign a :class:`LiquidityBucket` to each row using volume + OI percentiles.

    The spec (MODEL.md §4) says liquidity is based on *volume and open interest
    percentile*, not volume alone.  Both dimensions must agree on LIQUID for the
    row to be LIQUID; either dimension being THIN makes the row THIN.

    Parameters
    ----------
    volume, open_interest:
        Series of the same length (Bhavcopy Vol and OI columns).
    vol_thin_pct / oi_thin_pct:
        Rows below this percentile of their respective series are THIN.
    vol_liquid_pct / oi_liquid_pct:
        Rows above this percentile of their respective series are (candidate) LIQUID.

    Returns
    -------
    Series of :class:`LiquidityBucket` strings, same index as input.
    """
    # Use interpolation='lower' so that the quantile value is always an actual
    # data point.  This means a row exactly at the quantile is NOT below it,
    # so strict-less-than gives the correct "bottom N%" semantics.
    vol_q_thin   = volume.quantile(vol_thin_pct / 100, interpolation="lower")
    vol_q_liquid = volume.quantile(vol_liquid_pct / 100, interpolation="lower")
    oi_q_thin    = open_interest.quantile(oi_thin_pct / 100, interpolation="lower")
    oi_q_liquid  = open_interest.quantile(oi_liquid_pct / 100, interpolation="lower")

    def _bucket(v: float, oi: float) -> str:
        is_thin = v < vol_q_thin or oi < oi_q_thin
        if is_thin:
            return LiquidityBucket.THIN
        is_liquid = v > vol_q_liquid and oi > oi_q_liquid
        if is_liquid:
            return LiquidityBucket.LIQUID
        return LiquidityBucket.NORMAL

    return pd.Series(
        [_bucket(v, o) for v, o in zip(volume, open_interest)],
        index=volume.index,
        dtype=str,
    )


# ── z-score computation ───────────────────────────────────────────────────────

def compute_zscore_series(
    spread: pd.Series,
    lookback: int,
    *,
    min_periods: int | None = None,
) -> pd.Series:
    """Compute a rolling z-score for *spread* with window *lookback*.

    Uses ``min_periods = lookback`` by default so the z-score is ``nan`` for
    the first ``lookback - 1`` rows (no partial-window signals).

    *No look-ahead*: the rolling window is strictly backward-looking.

    Parameters
    ----------
    spread:
        Series of carry-adjusted spread values, indexed by trading date,
        sorted ascending (oldest first).
    lookback:
        Number of calendar rows (trading days) in the rolling window.
    min_periods:
        Override minimum periods.  Defaults to *lookback*.

    Returns
    -------
    Series of z-scores, same index as *spread*.  ``nan`` where std == 0 or
    where the window is incomplete.
    """
    if min_periods is None:
        min_periods = lookback

    roll_mean = spread.rolling(window=lookback, min_periods=min_periods).mean()
    roll_std  = spread.rolling(window=lookback, min_periods=min_periods).std(ddof=1)

    # avoid division by zero
    zscore = (spread - roll_mean) / roll_std.replace(0, float("nan"))
    return zscore


# ── config ────────────────────────────────────────────────────────────────────

@dataclass
class SignalConfig:
    """All tunable thresholds for the signal engine (MODEL.md §4, §7).

    Load this from the backtest config YAML; do not hard-code numbers here.
    """
    lookback: int = 60
    """Rolling window length in trading days."""

    z_entry: float = 2.0
    """Open a position when |z| >= z_entry."""

    z_exit: float = 0.5
    """Close on mean-reversion when |z| < z_exit."""

    z_stop: float = 3.5
    """Stop-loss: close if |z| exceeds this threshold on the wrong side
    (i.e. the spread moved further against us than z_stop)."""

    max_hold_days: int = 20
    """Maximum days to hold a position before forced exit."""

    exit_days_before_expiry: int = 5
    """Force exit if either leg has days_to_expiry <= this value."""

    tender_days: int = 5
    """Do not enter if either leg is within tender period (same as exit_days)."""

    min_expiry_gap_days: int = 0
    """Reject pairs with |expiry_gap_days| below this (usually 0 → accept exact matches)."""

    max_expiry_gap_days: int = 10
    """Reject pairs with |expiry_gap_days| above this (mirrors pairing.py default)."""

    max_positions: int = 4
    """Maximum simultaneous open positions across all pairs."""

    @classmethod
    def from_dict(cls, d: dict) -> "SignalConfig":
        """Build from a plain dict (e.g. loaded from YAML)."""
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ── position state machine ────────────────────────────────────────────────────

class _PositionState(Enum):
    FLAT   = "flat"
    LONG_A = "long_a"   # long A / short B
    LONG_B = "long_b"   # long B / short A


@dataclass
class _OpenPosition:
    direction: _PositionState
    entry_date: date
    entry_z: float
    hold_days: int = 0


def _exit_reason(
    pos: _OpenPosition,
    z: float,
    cfg: SignalConfig,
    dte_a: int,
    dte_b: int,
) -> Optional[str]:
    """Return an exit reason string, or None if the position should stay open."""
    # calendar exit — checked first, always safe
    if dte_a <= cfg.exit_days_before_expiry or dte_b <= cfg.exit_days_before_expiry:
        return "calendar"
    # z is NaN (window incomplete or zero-std) — cannot assess; force exit
    if math.isnan(z):
        return "no_z"
    # mean-reversion exit
    if abs(z) < cfg.z_exit:
        return "mean_reversion"
    # max hold
    if pos.hold_days >= cfg.max_hold_days:
        return "max_hold"
    # stop-loss: spread moved further against us
    if pos.direction == _PositionState.LONG_A and z < -cfg.z_stop:
        return "stop"
    if pos.direction == _PositionState.LONG_B and z > cfg.z_stop:
        return "stop"
    return None


# ── main signal generator ─────────────────────────────────────────────────────

# Column names emitted by generate_signals
_OUTPUT_COLS = [
    "trade_date", "symbol_a", "symbol_b",
    "expiry_a", "expiry_b", "expiry_gap_days",
    "px_a", "px_b",
    "raw_spread", "carry_adj_spread",
    "z_score",
    "liquidity_a", "liquidity_b",
    "dte_a", "dte_b",
    "signal_direction",   # +1, -1, or 0
    "position_state",     # flat / long_a / long_b
    "exit_reason",        # nan / "mean_reversion" / "calendar" / "stop" / "max_hold"
    "hold_days",
]


def generate_signals(
    pairs_df: pd.DataFrame,
    cfg: SignalConfig | None = None,
    *,
    liquidity_a_col: str = "liquidity_a",
    liquidity_b_col: str = "liquidity_b",
    dte_a_col: str = "dte_a",
    dte_b_col: str = "dte_b",
) -> pd.DataFrame:
    """Run the signal engine over a paired-spread DataFrame.

    Processes each (symbol_a, symbol_b, expiry_a, expiry_b) series
    independently, applying the rolling z-score and state machine.

    Parameters
    ----------
    pairs_df:
        Output of ``model.pairing.build_pairs_df``, augmented with:
        - ``liquidity_a``, ``liquidity_b``: :class:`LiquidityBucket` string
        - ``dte_a``, ``dte_b``: days to expiry for each leg (int)
        The DataFrame must be sorted by ``trade_date`` ascending.
    cfg:
        :class:`SignalConfig` instance.  Defaults to ``SignalConfig()``
        (uses default thresholds — *replace with config-loaded values*).

    Returns
    -------
    DataFrame with one row per (date, pair, expiry-pair), with all columns
    from *pairs_df* plus: ``z_score``, ``signal_direction``, ``position_state``,
    ``exit_reason``, ``hold_days``.
    """
    if cfg is None:
        cfg = SignalConfig()

    if pairs_df.empty:
        return pd.DataFrame(columns=_OUTPUT_COLS)

    required_input = {"trade_date", "symbol_a", "symbol_b", "expiry_a", "expiry_b",
                      "expiry_gap_days", "carry_adj_spread", "px_a", "px_b",
                      "raw_spread"}
    missing = required_input - set(pairs_df.columns)
    if missing:
        raise ValueError(f"generate_signals: missing columns in pairs_df: {sorted(missing)}")

    all_rows: list[dict] = []

    # group by the contract-pair key
    group_keys = ["symbol_a", "symbol_b", "expiry_a", "expiry_b"]
    for group_key, grp in pairs_df.groupby(group_keys, sort=False):
        sym_a, sym_b, exp_a, exp_b = group_key
        grp = grp.sort_values("trade_date").reset_index(drop=True)

        spread = grp["carry_adj_spread"]
        z_series = compute_zscore_series(spread, cfg.lookback)
        position: Optional[_OpenPosition] = None
        open_position_count = 0  # simplified: count per-series (global limit handled upstream)

        for i, row in grp.iterrows():
            z = z_series.iloc[i]
            gap = int(row["expiry_gap_days"])

            liq_a = row.get(liquidity_a_col, LiquidityBucket.NORMAL)
            liq_b = row.get(liquidity_b_col, LiquidityBucket.NORMAL)
            dte_a = int(row.get(dte_a_col, cfg.exit_days_before_expiry + 1))
            dte_b = int(row.get(dte_b_col, cfg.exit_days_before_expiry + 1))

            signal_direction = 0
            exit_reason_val: Optional[str] = None
            state = _PositionState.FLAT

            if position is not None:
                position.hold_days += 1
                reason = _exit_reason(position, z, cfg, dte_a, dte_b)
                if reason:
                    exit_reason_val = reason
                    position = None
                else:
                    state = position.direction

            # try to enter if flat and z is valid
            if position is None and not np.isnan(z):
                thin = (
                    liq_a == LiquidityBucket.THIN or str(liq_a) == LiquidityBucket.THIN.value
                    or liq_b == LiquidityBucket.THIN or str(liq_b) == LiquidityBucket.THIN.value
                )
                near_expiry = (
                    dte_a <= cfg.tender_days or dte_b <= cfg.tender_days
                )
                bad_gap = (
                    abs(gap) < cfg.min_expiry_gap_days
                    or abs(gap) > cfg.max_expiry_gap_days
                )
                can_enter = not thin and not near_expiry and not bad_gap

                if can_enter and z >= cfg.z_entry:
                    # A is rich → short A, long B → direction = LONG_B (= -1 signal)
                    signal_direction = -1
                    position = _OpenPosition(
                        direction=_PositionState.LONG_B,
                        entry_date=row["trade_date"],
                        entry_z=z,
                    )
                    state = _PositionState.LONG_B
                elif can_enter and z <= -cfg.z_entry:
                    # A is cheap → long A, short B → direction = LONG_A (= +1 signal)
                    signal_direction = 1
                    position = _OpenPosition(
                        direction=_PositionState.LONG_A,
                        entry_date=row["trade_date"],
                        entry_z=z,
                    )
                    state = _PositionState.LONG_A

            all_rows.append({
                **row.to_dict(),
                "z_score":          z,
                "signal_direction": signal_direction,
                "position_state":   state.value,
                "exit_reason":      exit_reason_val,
                "hold_days":        position.hold_days if position is not None else 0,
            })

    result = pd.DataFrame(all_rows)
    if result.empty:
        return pd.DataFrame(columns=_OUTPUT_COLS)
    return result.sort_values("trade_date").reset_index(drop=True)
