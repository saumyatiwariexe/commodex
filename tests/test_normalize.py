"""
tests/test_normalize.py
=======================
Unit tests for model/normalize.py (MODEL.md §1).

Hand-computed expected values
-----------------------------
GOLDM   close=60000, quote=10g, purity=995
        → (60000/10) * (999/995) = 6000 * 1.004020… = 6024.12…

GOLDTEN  close=6000, quote=10g, purity=999
        → (6000/10) * (999/999) = 600.0

GOLDGUINEA close=4800, quote=8g, purity=999
        → (4800/8) * 1.0 = 600.0

GOLDPETAL  close=600, quote=1g, purity=999
        → (600/1) * 1.0 = 600.0

All three 999-purity contracts at aligned prices produce the same px_per_gram_999.
"""

from __future__ import annotations

import math

import pytest

from model.normalize import (
    CONTRACTS,
    ContractMeta,
    normalize_df,
    normalize_price,
    normalize_price_by_symbol,
    normalize_row,
)


# ── normalize_price ───────────────────────────────────────────────────────────

class TestNormalizePrice:
    def test_goldm_hand_computed(self) -> None:
        meta = CONTRACTS["GOLDM"]
        result = normalize_price(60_000.0, meta)
        expected = (60_000.0 / 10) * (999 / 995)
        assert math.isclose(result, expected, rel_tol=1e-9)

    def test_goldten_hand_computed(self) -> None:
        meta = CONTRACTS["GOLDTEN"]
        result = normalize_price(6_000.0, meta)
        expected = 6_000.0 / 10  # purity = 999
        assert math.isclose(result, expected, rel_tol=1e-9)

    def test_goldguinea_hand_computed(self) -> None:
        meta = CONTRACTS["GOLDGUINEA"]
        result = normalize_price(4_800.0, meta)
        expected = 4_800.0 / 8
        assert math.isclose(result, expected, rel_tol=1e-9)

    def test_goldpetal_hand_computed(self) -> None:
        meta = CONTRACTS["GOLDPETAL"]
        result = normalize_price(600.0, meta)
        assert math.isclose(result, 600.0, rel_tol=1e-9)

    def test_999_purity_contracts_aligned(self) -> None:
        """At matched prices the three 999-purity contracts yield the same px."""
        px_ten = normalize_price(6_000.0, CONTRACTS["GOLDTEN"])
        px_guinea = normalize_price(4_800.0, CONTRACTS["GOLDGUINEA"])
        px_petal = normalize_price(600.0, CONTRACTS["GOLDPETAL"])
        assert math.isclose(px_ten, px_guinea, rel_tol=1e-9)
        assert math.isclose(px_ten, px_petal, rel_tol=1e-9)

    def test_zero_close_raises(self) -> None:
        with pytest.raises(ValueError, match="close must be > 0"):
            normalize_price(0.0, CONTRACTS["GOLDM"])

    def test_negative_close_raises(self) -> None:
        with pytest.raises(ValueError, match="close must be > 0"):
            normalize_price(-100.0, CONTRACTS["GOLDM"])

    def test_custom_meta(self) -> None:
        """Custom ContractMeta works correctly."""
        meta = ContractMeta(
            symbol="CUSTOM",
            trading_unit_grams=50,
            quote_grams=5,
            purity=990,
        )
        result = normalize_price(5_000.0, meta)
        expected = (5_000.0 / 5) * (999 / 990)
        assert math.isclose(result, expected, rel_tol=1e-9)


# ── normalize_price_by_symbol ─────────────────────────────────────────────────

class TestNormalizePriceBySymbol:
    def test_known_symbol(self) -> None:
        result = normalize_price_by_symbol("GOLDPETAL", 600.0)
        assert math.isclose(result, 600.0, rel_tol=1e-9)

    def test_symbol_stripped(self) -> None:
        """Bhavcopy pads symbols with spaces; stripping must work."""
        result = normalize_price_by_symbol("  GOLDPETAL  ", 600.0)
        assert math.isclose(result, 600.0, rel_tol=1e-9)

    def test_unknown_symbol_raises(self) -> None:
        with pytest.raises(KeyError, match="unknown symbol"):
            normalize_price_by_symbol("SILVER", 1000.0)

    def test_custom_contracts_map(self) -> None:
        custom_meta = ContractMeta(
            symbol="XGOLD",
            trading_unit_grams=100,
            quote_grams=10,
            purity=999,
        )
        result = normalize_price_by_symbol("XGOLD", 7_000.0, {"XGOLD": custom_meta})
        assert math.isclose(result, 700.0, rel_tol=1e-9)


# ── normalize_row ─────────────────────────────────────────────────────────────

class TestNormalizeRow:
    def test_basic(self) -> None:
        row = {"symbol": "GOLDPETAL", "close": 600.0}
        assert math.isclose(normalize_row(row), 600.0, rel_tol=1e-9)

    def test_padded_symbol(self) -> None:
        row = {"symbol": "GOLDM   ", "close": 60_000.0}
        expected = (60_000.0 / 10) * (999 / 995)
        assert math.isclose(normalize_row(row), expected, rel_tol=1e-9)

    def test_custom_column_names(self) -> None:
        row = {"sym": "GOLDTEN", "settlement": 6_000.0}
        result = normalize_row(row, symbol_col="sym", close_col="settlement")
        assert math.isclose(result, 600.0, rel_tol=1e-9)

    def test_missing_column_raises(self) -> None:
        with pytest.raises(KeyError):
            normalize_row({"symbol": "GOLDM"})  # missing "close"


# ── normalize_df ──────────────────────────────────────────────────────────────

class TestNormalizeDf:
    @pytest.fixture()
    def sample_df(self):  # type: ignore[no-untyped-def]
        import pandas as pd

        return pd.DataFrame(
            {
                "symbol": ["GOLDM", "GOLDTEN", "GOLDGUINEA", "GOLDPETAL"],
                "close": [60_000.0, 6_000.0, 4_800.0, 600.0],
            }
        )

    def test_adds_column(self, sample_df) -> None:  # type: ignore[no-untyped-def]
        result = normalize_df(sample_df)
        assert "px_per_gram_999" in result.columns

    def test_does_not_mutate_input(self, sample_df) -> None:  # type: ignore[no-untyped-def]
        _ = normalize_df(sample_df)
        assert "px_per_gram_999" not in sample_df.columns

    def test_goldm_value(self, sample_df) -> None:  # type: ignore[no-untyped-def]
        result = normalize_df(sample_df)
        expected = (60_000.0 / 10) * (999 / 995)
        assert math.isclose(result.loc[result["symbol"] == "GOLDM", "px_per_gram_999"].iloc[0], expected, rel_tol=1e-9)

    def test_999_purity_all_equal(self, sample_df) -> None:  # type: ignore[no-untyped-def]
        result = normalize_df(sample_df)
        px_ten = result.loc[result["symbol"] == "GOLDTEN", "px_per_gram_999"].iloc[0]
        px_guinea = result.loc[result["symbol"] == "GOLDGUINEA", "px_per_gram_999"].iloc[0]
        px_petal = result.loc[result["symbol"] == "GOLDPETAL", "px_per_gram_999"].iloc[0]
        assert math.isclose(px_ten, px_guinea, rel_tol=1e-9)
        assert math.isclose(px_ten, px_petal, rel_tol=1e-9)

    def test_bad_close_becomes_nan(self) -> None:  # type: ignore[no-untyped-def]
        import math as _math
        import pandas as pd

        df = pd.DataFrame({"symbol": ["GOLDM", "GOLDM"], "close": [-1.0, 60_000.0]})
        result = normalize_df(df)
        assert _math.isnan(result["px_per_gram_999"].iloc[0])
        assert not _math.isnan(result["px_per_gram_999"].iloc[1])

    def test_custom_out_col(self, sample_df) -> None:  # type: ignore[no-untyped-def]
        result = normalize_df(sample_df, out_col="norm_px")
        assert "norm_px" in result.columns
        assert "px_per_gram_999" not in result.columns
