"""
model/normalize.py
==================
Price normalisation: convert every settlement close to INR per gram of
999-purity gold (MODEL.md §1).

Formula
-------
    px_per_gram_999 = (close / quote_grams) * (999 / purity)

Contract specs (must be verified against the MCX spec page before the demo —
AGENTS.md non-negotiable 10 / MODEL.md §1).  All values live in
``contracts_meta.yaml``; this module ships a ``CONTRACTS`` default that
mirrors the doc-level spec so that tests and notebooks can run without the
YAML file.

Public API
----------
  normalize_price(symbol, close) -> float
  normalize_row(row)             -> float   row is a dict with "symbol" and "close"
  normalize_df(df)               -> pd.DataFrame   adds column "px_per_gram_999"
  load_contract_meta(path)       -> dict[str, ContractMeta]
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

logger = logging.getLogger(__name__)

# ── contract metadata ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ContractMeta:
    """Specification for a single MCX gold futures symbol."""

    symbol: str
    """MCX ticker exactly as it appears in Bhavcopy (strip padding before use)."""

    trading_unit_grams: float
    """Grams of gold per lot (e.g. 100 for GOLDM)."""

    quote_grams: float
    """Grams for which the settlement price is quoted (e.g. 10 for GOLDM)."""

    purity: int
    """Purity in parts-per-thousand (e.g. 995 for GOLDM, 999 for the rest)."""


# Default spec — mirrors MODEL.md §1 and PROBLEM_STATEMENT.md contract table.
# [Likely] correct; verify against https://www.mcxindia.com/products/bullion/gold
# before the demo and regenerate via load_contract_meta() if anything differs.
CONTRACTS: dict[str, ContractMeta] = {
    "GOLDM": ContractMeta(
        symbol="GOLDM",
        trading_unit_grams=100,
        quote_grams=10,
        purity=995,
    ),
    "GOLDTEN": ContractMeta(
        symbol="GOLDTEN",
        trading_unit_grams=10,
        quote_grams=10,
        purity=999,
    ),
    "GOLDGUINEA": ContractMeta(
        symbol="GOLDGUINEA",
        trading_unit_grams=8,
        quote_grams=8,
        purity=999,
    ),
    "GOLDPETAL": ContractMeta(
        symbol="GOLDPETAL",
        trading_unit_grams=1,
        quote_grams=1,
        purity=999,
    ),
}


def load_contract_meta(path: Path | str) -> dict[str, ContractMeta]:
    """Load contract specs from *contracts_meta.yaml* and return a symbol map.

    The YAML file should have the structure::

        contracts:
          - symbol: GOLDM
            trading_unit_grams: 100
            quote_grams: 10
            purity: 995
          ...

    Unknown symbols are logged as warnings and skipped.
    Raises ``FileNotFoundError`` if *path* does not exist.
    Raises ``KeyError`` / ``ValueError`` if required fields are missing or
    have wrong types.
    """
    try:
        import yaml  # pyyaml; optional for pure-model use
    except ImportError as exc:
        raise ImportError(
            "pyyaml is required to load contracts_meta.yaml. "
            "Install it with: pip install pyyaml"
        ) from exc

    path = Path(path)
    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    result: dict[str, ContractMeta] = {}
    for item in raw["contracts"]:
        symbol: str = str(item["symbol"]).strip()
        if not symbol:
            logger.warning("load_contract_meta: skipping entry with empty symbol: %r", item)
            continue
        meta = ContractMeta(
            symbol=symbol,
            trading_unit_grams=float(item["trading_unit_grams"]),
            quote_grams=float(item["quote_grams"]),
            purity=int(item["purity"]),
        )
        result[symbol] = meta
        logger.debug("load_contract_meta: loaded %s", meta)

    return result


# ── core formula ──────────────────────────────────────────────────────────────

def normalize_price(
    close: float,
    meta: ContractMeta,
) -> float:
    """Return INR per gram of 999-purity gold for *close*.

    ``close`` is the exchange settlement price (INR quoted per
    ``meta.quote_grams`` grams of gold at ``meta.purity`` purity).

    Raises ``ValueError`` if *close* is not strictly positive.
    """
    if close <= 0:
        raise ValueError(
            f"normalize_price: close must be > 0, got {close!r} for {meta.symbol!r}"
        )
    return (close / meta.quote_grams) * (999 / meta.purity)


def normalize_price_by_symbol(
    symbol: str,
    close: float,
    contracts: dict[str, ContractMeta] | None = None,
) -> float:
    """Convenience wrapper: look up *symbol* in *contracts* and normalize.

    *symbol* is stripped of whitespace before lookup (Bhavcopy pads symbols).
    Raises ``KeyError`` if the symbol is unknown.
    Raises ``ValueError`` if close is not strictly positive.
    """
    contracts = contracts or CONTRACTS
    key = symbol.strip()
    if key not in contracts:
        raise KeyError(
            f"normalize_price_by_symbol: unknown symbol {key!r}. "
            f"Known: {sorted(contracts)}"
        )
    return normalize_price(close, contracts[key])


# ── dict / DataFrame helpers ──────────────────────────────────────────────────

def normalize_row(
    row: dict[str, object],
    contracts: dict[str, ContractMeta] | None = None,
    *,
    symbol_col: str = "symbol",
    close_col: str = "close",
) -> float:
    """Normalize a single row dict; returns the float px_per_gram_999.

    Raises ``KeyError`` if columns or symbol are missing.
    Raises ``ValueError`` if close is non-positive.
    """
    symbol = str(row[symbol_col]).strip()
    close = float(row[close_col])  # type: ignore[arg-type]
    return normalize_price_by_symbol(symbol, close, contracts)


def normalize_df(
    df: "pd.DataFrame",
    contracts: dict[str, ContractMeta] | None = None,
    *,
    symbol_col: str = "symbol",
    close_col: str = "close",
    out_col: str = "px_per_gram_999",
) -> "pd.DataFrame":
    """Add *out_col* to *df* with INR-per-gram-999 prices.

    Returns a **copy**; the original DataFrame is not modified.
    Raises ``KeyError`` for unknown symbols; logs a warning and skips rows
    with non-positive close values, inserting ``float('nan')`` for them.

    This function imports pandas lazily so the module can be loaded in
    environments that don't have it (e.g., pure-model unit tests with fixtures).
    """
    import pandas as pd  # noqa: PLC0415  (lazy import intentional)

    contracts = contracts or CONTRACTS
    result = df.copy()

    def _safe_normalize(row: "pd.Series") -> float:  # type: ignore[type-arg]
        try:
            return normalize_row(row, contracts, symbol_col=symbol_col, close_col=close_col)
        except ValueError as exc:
            logger.warning("normalize_df: skipping row — %s", exc)
            return float("nan")

    result[out_col] = result.apply(_safe_normalize, axis=1)
    return result
