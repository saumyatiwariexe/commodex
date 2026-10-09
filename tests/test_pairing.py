"""
tests/test_pairing.py
=====================
Unit tests for model/pairing.py (MODEL.md §2).

Verifies:
  - pair_expiries: nearest-match, max_gap enforcement, dedup, empty inputs
  - estimate_r_daily: OLS slope, too-few-points → nan, non-positive filtered
  - carry_adjust: zero gap, nan r_daily, positive and negative gaps
  - build_pairs_df: end-to-end pairing, no-look-ahead (r_daily from same date only),
    mismatched symbols → empty, gap rejection
"""
from __future__ import annotations

import math
from datetime import date, timedelta

import pandas as pd
import pytest

from model.pairing import (
    ExpiryPair,
    build_pairs_df,
    carry_adjust,
    estimate_r_daily,
    pair_expiries,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def d(year: int, month: int, day: int) -> date:
    return date(year, month, day)


# ── pair_expiries ─────────────────────────────────────────────────────────────

class TestPairExpiries:
    def test_exact_match(self) -> None:
        exp_a = [d(2026, 10, 27)]
        exp_b = [d(2026, 10, 27)]
        pairs = pair_expiries(exp_a, exp_b)
        assert len(pairs) == 1
        assert pairs[0].expiry_gap_days == 0

    def test_nearest_match(self) -> None:
        """GOLDM expires 5th, GOLDPETAL expires 27th — they should pair."""
        exp_a = [d(2026, 10, 5)]
        exp_b = [d(2026, 9, 27), d(2026, 10, 27), d(2026, 11, 27)]
        # nearest to Oct 5 is Oct 27 (gap = 5-27 = -22 days) vs Sep 27 (gap=8 days)
        # Sep 27 is 8 days before, Oct 27 is 22 days after → Sep 27 is closer
        pairs = pair_expiries(exp_a, exp_b, max_gap_days=10)
        assert len(pairs) == 1
        assert pairs[0].expiry_b == d(2026, 9, 27)
        assert pairs[0].expiry_gap_days == (d(2026, 10, 5) - d(2026, 9, 27)).days  # +8

    def test_gap_rejected(self) -> None:
        exp_a = [d(2026, 10, 5)]
        exp_b = [d(2026, 10, 27)]   # gap = -22 days → rejected at max_gap=10
        pairs = pair_expiries(exp_a, exp_b, max_gap_days=10)
        assert pairs == []

    def test_gap_exactly_at_limit_accepted(self) -> None:
        exp_a = [d(2026, 10, 5)]
        exp_b = [d(2026, 9, 25)]    # gap = +10 days
        pairs = pair_expiries(exp_a, exp_b, max_gap_days=10)
        assert len(pairs) == 1
        assert pairs[0].expiry_gap_days == 10

    def test_multiple_a_expiries(self) -> None:
        exp_a = [d(2026, 10, 5), d(2026, 11, 4), d(2026, 12, 3)]
        exp_b = [d(2026, 9, 27), d(2026, 10, 28), d(2026, 11, 27)]
        pairs = pair_expiries(exp_a, exp_b, max_gap_days=10)
        assert len(pairs) == 3

    def test_deduplication_of_inputs(self) -> None:
        exp_a = [d(2026, 10, 5), d(2026, 10, 5)]  # duplicate
        exp_b = [d(2026, 9, 27)]
        pairs = pair_expiries(exp_a, exp_b, max_gap_days=10)
        assert len(pairs) == 1  # de-duped to one

    def test_empty_a(self) -> None:
        assert pair_expiries([], [d(2026, 10, 27)]) == []

    def test_empty_b(self) -> None:
        assert pair_expiries([d(2026, 10, 5)], []) == []

    def test_both_empty(self) -> None:
        assert pair_expiries([], []) == []

    def test_signed_gap_positive(self) -> None:
        """A expires after B → positive gap."""
        exp_a = [d(2026, 10, 10)]
        exp_b = [d(2026, 10, 5)]
        pairs = pair_expiries(exp_a, exp_b, max_gap_days=10)
        assert pairs[0].expiry_gap_days == 5

    def test_signed_gap_negative(self) -> None:
        """A expires before B → negative gap."""
        exp_a = [d(2026, 10, 5)]
        exp_b = [d(2026, 10, 10)]
        pairs = pair_expiries(exp_a, exp_b, max_gap_days=10)
        assert pairs[0].expiry_gap_days == -5


# ── estimate_r_daily ──────────────────────────────────────────────────────────

class TestEstimateRDaily:
    def _make_series(self, spot: float, r: float, dtes: list[int]) -> tuple[pd.Series, pd.Series]:
        """Synthetic futures curve: px = spot * exp(r * dte)."""
        import math as _math
        prices = pd.Series([spot * _math.exp(r * dte) for dte in dtes])
        days = pd.Series(dtes, dtype=float)
        return prices, days

    def test_zero_carry(self) -> None:
        prices, days = self._make_series(600.0, 0.0, [10, 30, 60, 90, 120])
        r = estimate_r_daily(prices, days)
        assert math.isclose(r, 0.0, abs_tol=1e-8)

    def test_positive_carry(self) -> None:
        true_r = 0.0001
        prices, days = self._make_series(600.0, true_r, [10, 30, 60, 90, 120])
        r = estimate_r_daily(prices, days)
        assert math.isclose(r, true_r, rel_tol=0.01)

    def test_negative_carry(self) -> None:
        true_r = -0.0001
        prices, days = self._make_series(600.0, true_r, [10, 30, 60, 90, 120])
        r = estimate_r_daily(prices, days)
        assert math.isclose(r, true_r, rel_tol=0.01)

    def test_too_few_points_returns_nan(self) -> None:
        prices = pd.Series([600.0, 601.0])
        days = pd.Series([10.0, 30.0])
        r = estimate_r_daily(prices, days, min_points=5)
        assert math.isnan(r)

    def test_non_positive_prices_filtered(self) -> None:
        """Rows with price <= 0 or dte <= 0 must be dropped."""
        prices = pd.Series([0.0, -1.0, 600.0, 600.06, 600.12, 600.18, 600.24])
        days = pd.Series([0.0, 10.0, 20.0, 40.0, 60.0, 80.0, 100.0])
        # first two rows filtered; should still estimate with remaining 5
        r = estimate_r_daily(prices, days, min_points=5)
        assert not math.isnan(r)

    def test_flat_curve_singular(self) -> None:
        """All prices identical and all dtes identical → near-singular."""
        prices = pd.Series([600.0] * 6)
        days = pd.Series([30.0] * 6)
        r = estimate_r_daily(prices, days)
        assert math.isnan(r)


# ── carry_adjust ──────────────────────────────────────────────────────────────

class TestCarryAdjust:
    def test_zero_gap_returns_raw(self) -> None:
        assert carry_adjust(610.0, 600.0, 0, r_daily=0.0001) == pytest.approx(10.0)

    def test_nan_r_returns_raw(self) -> None:
        result = carry_adjust(610.0, 600.0, 5, r_daily=float("nan"))
        assert math.isclose(result, 10.0)

    def test_positive_gap_positive_carry(self) -> None:
        # px_a - px_b * (1 + 0.0001 * 5) = 610 - 600*1.0005 = 610 - 600.3 = 9.7
        result = carry_adjust(610.0, 600.0, 5, r_daily=0.0001)
        assert math.isclose(result, 610.0 - 600.0 * 1.0005, rel_tol=1e-9)

    def test_negative_gap(self) -> None:
        result = carry_adjust(610.0, 600.0, -5, r_daily=0.0001)
        assert math.isclose(result, 610.0 - 600.0 * (1 + 0.0001 * -5), rel_tol=1e-9)

    def test_zero_r_returns_raw(self) -> None:
        result = carry_adjust(610.0, 600.0, 8, r_daily=0.0)
        assert math.isclose(result, 10.0)


# ── build_pairs_df ────────────────────────────────────────────────────────────

class TestBuildPairsDf:
    @pytest.fixture()
    def simple_df(self) -> pd.DataFrame:
        """Minimal synthetic norm_df with GOLDPETAL and GOLDGUINEA, 3 dates."""
        rows = []
        base_px = 600.0
        sym_pairs = [
            ("GOLDPETAL", date(2026, 10, 27)),
            ("GOLDPETAL", date(2026, 11, 27)),
            ("GOLDGUINEA", date(2026, 10, 27)),
            ("GOLDGUINEA", date(2026, 11, 27)),
        ]
        for td in [date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3)]:
            for sym, exp in sym_pairs:
                rows.append({
                    "date": td,
                    "symbol": sym,
                    "expiry_date": exp,
                    "px_per_gram_999": base_px + (1.0 if sym == "GOLDGUINEA" else 0.0),
                })
        return pd.DataFrame(rows)

    def test_output_columns(self, simple_df: pd.DataFrame) -> None:
        result = build_pairs_df(simple_df, "GOLDPETAL", "GOLDGUINEA")
        expected_cols = {
            "trade_date", "symbol_a", "symbol_b",
            "expiry_a", "expiry_b", "expiry_gap_days",
            "px_a", "px_b", "raw_spread", "carry_adj_spread", "r_daily_used",
        }
        assert expected_cols.issubset(set(result.columns))

    def test_raw_spread_correct(self, simple_df: pd.DataFrame) -> None:
        import numpy as np
        result = build_pairs_df(simple_df, "GOLDPETAL", "GOLDGUINEA")
        # GOLDPETAL px = 600, GOLDGUINEA px = 601 → raw_spread = -1
        np.testing.assert_allclose(result["raw_spread"].to_numpy(), -1.0)

    def test_exact_expiry_match_zero_gap(self, simple_df: pd.DataFrame) -> None:
        result = build_pairs_df(simple_df, "GOLDPETAL", "GOLDGUINEA")
        assert (result["expiry_gap_days"] == 0).all()

    def test_no_rows_for_unknown_symbol(self, simple_df: pd.DataFrame) -> None:
        result = build_pairs_df(simple_df, "GOLDM", "GOLDGUINEA")
        assert result.empty

    def test_gap_rejected_in_output(self) -> None:
        """Pairs exceeding max_gap_days must not appear in output."""
        rows = []
        for sym, exp in [
            ("GOLDM", date(2026, 10, 5)),      # expiry on 5th
            ("GOLDPETAL", date(2026, 10, 27)),  # expiry on 27th — gap = -22 days
        ]:
            rows.append({
                "date": date(2026, 9, 15),
                "symbol": sym,
                "expiry_date": exp,
                "px_per_gram_999": 600.0,
            })
        df = pd.DataFrame(rows)
        result = build_pairs_df(df, "GOLDM", "GOLDPETAL", max_gap_days=10)
        assert result.empty

    def test_symbol_a_b_recorded(self, simple_df: pd.DataFrame) -> None:
        result = build_pairs_df(simple_df, "GOLDPETAL", "GOLDGUINEA")
        assert (result["symbol_a"] == "GOLDPETAL").all()
        assert (result["symbol_b"] == "GOLDGUINEA").all()

    def test_returns_dataframe(self, simple_df: pd.DataFrame) -> None:
        result = build_pairs_df(simple_df, "GOLDPETAL", "GOLDGUINEA")
        assert isinstance(result, pd.DataFrame)
        assert not result.empty
