"""
model/sizing.py
===============
Position sizing and hedge residual calculation (MODEL.md §5).

Lot sizes differ drastically across MCX gold contracts:
  GOLDM      = 100 g
  GOLDTEN    =  10 g
  GOLDGUINEA =   8 g
  GOLDPETAL  =   1 g

To match notional value, a GOLDM lot corresponds to 100 GOLDPETAL lots, but
often perfect matching isn't possible (e.g. 1 GOLDM vs GOLDGUINEA: 100g / 8g =
12.5 lots). We must trade whole lots. The unhedged remainder is directional
exposure to gold.

Public API
----------
  match_lots()        – given a target total grams, return whole lots for A and B
  hedge_residual()    – compute the unhedged gold exposure in grams
"""

from __future__ import annotations

import math
from typing import Tuple


def match_lots(
    target_grams: float,
    unit_grams_a: float,
    unit_grams_b: float,
) -> Tuple[int, int]:
    """Calculate the integer number of lots for A and B to best match the target.

    We simply round to the nearest whole lot for both legs independently to get
    as close to the `target_grams` notional as possible without fractional lots.

    Parameters
    ----------
    target_grams:
        The desired total gold exposure per leg (e.g., 100.0 grams).
    unit_grams_a, unit_grams_b:
        Lot size in grams for contract A and contract B.

    Returns
    -------
    (lots_a, lots_b) as integers.
    """
    if target_grams <= 0 or unit_grams_a <= 0 or unit_grams_b <= 0:
        raise ValueError("Target and unit grams must be strictly positive.")

    lots_a = round(target_grams / unit_grams_a)
    lots_b = round(target_grams / unit_grams_b)

    # If the target is so small it rounds to 0 for a large contract, bump it to 1
    # so we always output a valid position if this function is called.
    if lots_a == 0:
        lots_a = 1
    if lots_b == 0:
        lots_b = 1

    return lots_a, lots_b


def hedge_residual(
    lots_a: int,
    unit_grams_a: float,
    lots_b: int,
    unit_grams_b: float,
) -> float:
    """Calculate the unhedged residual in grams.

    If we are long A and short B, the net physical position is:
        (lots_a * unit_grams_a) - (lots_b * unit_grams_b)

    Returns
    -------
    Net unhedged grams (signed).
    """
    return (lots_a * unit_grams_a) - (lots_b * unit_grams_b)
