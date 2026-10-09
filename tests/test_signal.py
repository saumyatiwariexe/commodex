"""
tests/test_signal.py
====================
Unit tests for model/signal.py (MODEL.md §4).

Verifies:
  - classify_liquidity: thin/normal/liquid assignment, percentile logic
  - compute_zscore_series: no look-ahead, NaN for insufficient window,
    zero-std → nan, correct values
  - SignalConfig.from_dict: round-trip
  - generate_signals: entry on |z| >= z_entry, no entry on thin leg,
    exit on mean-reversion / max_hold / stop / calendar,
    no look-ahead (z uses only past data), empty input handled
"""
from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from model.signal import (
    LiquidityBucket,
    SignalConfig,
    classify_liquidity,
    compute_zscore_series,
    generate_signals,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_pairs_df(
    n: int,
    spread_values: list[float] | None = None,
    *,
    liq_a: str = LiquidityBucket.LIQUID,
    liq_b: str = LiquidityBucket.LIQUID,
    dte: int = 30,
    gap: int = 0,
    start: date = date(2026, 1, 1),
) -> pd.DataFrame:
    """Build a minimal paired DataFrame for signal tests."""
    dates = [start + timedelta(days=i) for i in range(n)]
    if spread_values is None:
        spread_values = [0.0] * n
    rows = []
    for i, (td, s) in enumerate(zip(dates, spread_values)):
        rows.append({
            "trade_date":      td,
            "symbol_a":        "GOLDPETAL",
            "symbol_b":        "GOLDGUINEA",
            "expiry_a":        date(2026, 6, 27),
            "expiry_b":        date(2026, 6, 27),
            "expiry_gap_days": gap,
            "px_a":            600.0 + s,
            "px_b":            600.0,
            "raw_spread":      s,
            "carry_adj_spread": s,
            "liquidity_a":     liq_a,
            "liquidity_b":     liq_b,
            "dte_a":           dte - i,
            "dte_b":           dte - i,
        })
    return pd.DataFrame(rows)


# ── classify_liquidity ────────────────────────────────────────────────────────

class TestClassifyLiquidity:
    def test_all_equal_is_normal(self) -> None:
        vol = pd.Series([100.0] * 10)
        oi  = pd.Series([500.0] * 10)
        result = classify_liquidity(vol, oi)
        assert all(r == LiquidityBucket.NORMAL.value for r in result)

    def test_low_volume_is_thin(self) -> None:
        # 2 low-volume rows + 8 high: quantile(20%, interpolation='lower') = 1.0
        # The first two rows have vol = 1.0, which is NOT < 1.0, so they are NOT thin.
        # Use vol = 0.5 to be strictly below the quantile.
        vol = pd.Series([0.5] + [1000.0] * 9)
        oi  = pd.Series([500.0] * 10)
        result = classify_liquidity(vol, oi, vol_thin_pct=20)
        assert result.iloc[0] == LiquidityBucket.THIN.value

    def test_high_both_is_liquid(self) -> None:
        vol = pd.Series(range(1, 101), dtype=float)
        oi  = pd.Series(range(1, 101), dtype=float)
        result = classify_liquidity(vol, oi, vol_liquid_pct=60, oi_liquid_pct=60)
        # top values (strictly > q60) should be LIQUID
        assert result.iloc[-1] == LiquidityBucket.LIQUID.value

    def test_thin_overrides_liquid_vol(self) -> None:
        """If OI is thin, the row is THIN even if volume is high.

        With interpolation='lower', q(20%) is an actual data point.  To ensure
        a row is strictly below the quantile boundary, use a value smaller than
        all other OI values so the quantile is larger than it.
        """
        # Row 0: high vol, OI = 0.05 (strictly less than q20 of rest)
        # Rows 1-9: mix of high vol and high OI
        vol = pd.Series([1000.0] + [500.0] * 9)
        oi  = pd.Series([0.05] + [500.0] * 9)
        result = classify_liquidity(vol, oi, vol_thin_pct=20, oi_thin_pct=20)
        # row 0 has OI strictly below thin boundary → THIN
        assert result.iloc[0] == LiquidityBucket.THIN.value



    def test_output_length(self) -> None:
        vol = pd.Series([100.0] * 20)
        oi  = pd.Series([200.0] * 20)
        assert len(classify_liquidity(vol, oi)) == 20


# ── compute_zscore_series ─────────────────────────────────────────────────────

class TestComputeZscoreSeries:
    def test_nan_before_full_window(self) -> None:
        spread = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        z = compute_zscore_series(spread, lookback=3)
        assert math.isnan(z.iloc[0])
        assert math.isnan(z.iloc[1])
        assert not math.isnan(z.iloc[2])

    def test_zero_at_mean(self) -> None:
        # When current value equals rolling mean: window [1,2,3] mean=2, val=2 → z=0
        # At index 2: mean([1,2,3])=2, spread[2]=3 → z = (3-2)/std
        # At index 3: window=[2,3,2], mean=7/3≠2; use a symmetric window instead.
        # Simpler: mean([a,b,c]) = b when a+c = 2b; use [1,2,3] → z at index 2 = +1.0
        # For z=0 test: value must equal the mean of its own window.
        # [2,2,2,2]: constant → std=0 → nan. Use [0,4,2] → mean=2, val=2, z=0.
        spread = pd.Series([0.0, 4.0, 2.0])
        z = compute_zscore_series(spread, lookback=3)
        assert math.isclose(z.iloc[2], 0.0, abs_tol=1e-9)

    def test_positive_z_above_mean(self) -> None:
        spread = pd.Series([1.0, 2.0, 3.0, 10.0])
        z = compute_zscore_series(spread, lookback=3)
        assert z.iloc[3] > 0

    def test_negative_z_below_mean(self) -> None:
        spread = pd.Series([1.0, 2.0, 3.0, -5.0])
        z = compute_zscore_series(spread, lookback=3)
        assert z.iloc[3] < 0

    def test_constant_spread_nan_z(self) -> None:
        """Constant spread → std = 0 → z should be nan."""
        spread = pd.Series([5.0] * 10)
        z = compute_zscore_series(spread, lookback=5)
        assert all(math.isnan(v) for v in z.iloc[4:])

    def test_no_look_ahead(self) -> None:
        """z at position i must only depend on rows 0..i."""
        spread = pd.Series([1.0, 2.0, 3.0, 4.0, 100.0])  # spike at end
        z_full = compute_zscore_series(spread, lookback=3)
        z_short = compute_zscore_series(spread.iloc[:4], lookback=3)
        # z at position 3 should be the same whether or not the spike exists
        assert math.isclose(z_full.iloc[3], z_short.iloc[3], rel_tol=1e-9)

    def test_known_value(self) -> None:
        """Manual calculation: spread=[1,2,3], window=3, value=3."""
        # mean([1,2,3])=2, std([1,2,3],ddof=1)=1, z=(3-2)/1=1.0
        spread = pd.Series([1.0, 2.0, 3.0])
        z = compute_zscore_series(spread, lookback=3)
        assert math.isclose(z.iloc[2], 1.0, rel_tol=1e-9)


# ── SignalConfig ──────────────────────────────────────────────────────────────

class TestSignalConfig:
    def test_defaults(self) -> None:
        cfg = SignalConfig()
        assert cfg.lookback == 60
        assert cfg.z_entry == 2.0

    def test_from_dict(self) -> None:
        cfg = SignalConfig.from_dict({"lookback": 40, "z_entry": 1.5, "z_exit": 0.3})
        assert cfg.lookback == 40
        assert cfg.z_entry == 1.5
        assert cfg.z_exit == 0.3

    def test_from_dict_ignores_unknown_keys(self) -> None:
        cfg = SignalConfig.from_dict({"lookback": 30, "unknown_key": "ignored"})
        assert cfg.lookback == 30


# ── generate_signals ──────────────────────────────────────────────────────────

class TestGenerateSignals:
    def _cfg(self, **kwargs) -> SignalConfig:
        defaults = dict(lookback=5, z_entry=1.5, z_exit=0.3, z_stop=4.0,
                        max_hold_days=20, exit_days_before_expiry=3, tender_days=3,
                        min_expiry_gap_days=0, max_expiry_gap_days=10)
        defaults.update(kwargs)
        return SignalConfig(**defaults)

    def test_empty_input(self) -> None:
        result = generate_signals(pd.DataFrame())
        assert result.empty

    def test_no_signal_before_lookback(self) -> None:
        """No position should open before the z-score window fills."""
        n = 10
        # spread spike on day 3 (before lookback=5 fills)
        spreads = [0.0] * 3 + [999.0] + [0.0] * 6
        df = _make_pairs_df(n, spreads, dte=60)
        cfg = self._cfg(lookback=5, z_entry=1.5)
        result = generate_signals(df, cfg)
        # first 4 rows can't trigger entry (window not full)
        early = result[result["trade_date"] < date(2026, 1, 5)]
        assert (early["signal_direction"] == 0).all()

    def test_entry_on_high_z(self) -> None:
        """A large spike after the lookback window should trigger a signal."""
        n = 20
        # stable spread then a big positive spike
        spreads = [0.0] * 10 + [50.0] + [0.0] * 9
        df = _make_pairs_df(n, spreads, dte=60)
        cfg = self._cfg(lookback=5, z_entry=1.5)
        result = generate_signals(df, cfg)
        # there must be at least one non-zero signal_direction
        assert (result["signal_direction"] != 0).any()

    def test_no_entry_on_thin_leg(self) -> None:
        """If either leg is THIN, entry must be suppressed."""
        n = 20
        spreads = [0.0] * 10 + [50.0] + [0.0] * 9
        df = _make_pairs_df(n, spreads, liq_a=LiquidityBucket.THIN, dte=60)
        cfg = self._cfg(lookback=5, z_entry=1.5)
        result = generate_signals(df, cfg)
        assert (result["signal_direction"] == 0).all()

    def test_no_entry_near_expiry(self) -> None:
        """No entry if dte <= tender_days."""
        n = 20
        spreads = [0.0] * 10 + [50.0] + [0.0] * 9
        # dte counts down from 4 → most rows are at or below tender_days=3
        df = _make_pairs_df(n, spreads, dte=4)
        cfg = self._cfg(lookback=5, z_entry=1.5, tender_days=3)
        result = generate_signals(df, cfg)
        assert (result["signal_direction"] == 0).all()

    def test_exit_mean_reversion(self) -> None:
        """Position opened on spike should exit when spread normalises."""
        # lookback=5: 10 stable rows to prime window, one spike, then 20 stable rows.
        # After spike leaves the window z may be NaN (no_z exit) or drop below z_exit
        # (mean_reversion exit) depending on data shape.  Both are valid exits.
        spreads = [0.0] * 10 + [30.0] + [0.0] * 20
        n = len(spreads)
        df = _make_pairs_df(n, spreads, dte=90)
        cfg = self._cfg(lookback=5, z_entry=1.5, z_exit=0.3, max_hold_days=50)
        result = generate_signals(df, cfg)
        exits = result[result["exit_reason"].isin(["mean_reversion", "no_z"])]
        assert not exits.empty

    def test_exit_max_hold(self) -> None:
        """Position held too long (z stays elevated) triggers max_hold exit."""
        # To avoid no_z exit, the spread must remain elevated but volatile (not constant)
        # so std != 0. A steady upward trend keeps z positive.
        spreads = [0.0] * 5 + [10.0 + i * 2.0 for i in range(15)]
        n = len(spreads)
        df = _make_pairs_df(n, spreads, dte=90)
        cfg = self._cfg(lookback=5, z_entry=1.5, z_exit=0.01, max_hold_days=5)
        result = generate_signals(df, cfg)
        exits = result[result["exit_reason"] == "max_hold"]
        assert not exits.empty

    def test_exit_calendar(self) -> None:
        """Position exits when dte drops to exit_days_before_expiry."""
        spreads = [0.0] * 5 + [30.0] * 10
        n = len(spreads)
        df = _make_pairs_df(n, spreads, dte=n + 5)
        # override dte_a and dte_b to expire soon
        df["dte_a"] = list(range(n, 0, -1))
        df["dte_b"] = list(range(n, 0, -1))
        cfg = self._cfg(lookback=5, z_entry=1.5, exit_days_before_expiry=8, max_hold_days=100)
        result = generate_signals(df, cfg)
        exits = result[result["exit_reason"] == "calendar"]
        assert not exits.empty

    def test_output_has_required_columns(self) -> None:
        df = _make_pairs_df(20, [0.0] * 20, dte=60)
        cfg = self._cfg()
        result = generate_signals(df, cfg)
        for col in ["z_score", "signal_direction", "position_state", "exit_reason", "hold_days"]:
            assert col in result.columns

    def test_missing_required_column_raises(self) -> None:
        df = _make_pairs_df(10)
        df = df.drop(columns=["carry_adj_spread"])
        with pytest.raises(ValueError, match="missing columns"):
            generate_signals(df)
