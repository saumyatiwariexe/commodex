"""
model/pairing.py
================
Expiry-aware contract pairing and carry adjustment (MODEL.md §2).

The core problem
----------------
GOLDM expires around the 3rd–5th of the month.  The other three contracts
expire around the 27th–31st.  Comparing by *contract month* injects carry
into the spread and produces false signals.

Rules (MODEL.md §2)
-------------------
1. For contracts A and B on date t, pair each expiry of A with the expiry of
   B *nearest in calendar days*.
2. Record ``expiry_gap_days`` (signed: positive means A expires after B).
3. Reject pairs whose |expiry_gap_days| > ``max_gap_days`` (default 10).
4. Carry adjustment (applied only when the gap is non-zero)::

       carry_adj_spread = px_a - px_b * (1 + r_daily * expiry_gap_days_signed)

   where ``r_daily`` is estimated from the term structure of a *single* family
   using only data up to t (no look-ahead).  If it cannot be estimated stably,
   fall back to *excluding* wide-gap pairs rather than guessing.

Public API
----------
  PairedRow           – dataclass for one paired observation
  pair_expiries()     – given two sets of expiries, return best-match pairs
  carry_adjust()      – apply carry adjustment to a spread
  estimate_r_daily()  – estimate daily carry from a single symbol's term struct
  build_pairs_df()    – high-level: takes a normalised DataFrame, returns pairs
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date
from typing import NamedTuple

import pandas as pd

logger = logging.getLogger(__name__)

# ── types ─────────────────────────────────────────────────────────────────────

class ExpiryPair(NamedTuple):
    """A single matched pair of expiry dates across two symbols."""
    expiry_a: date
    expiry_b: date
    expiry_gap_days: int   # signed: a - b in calendar days


@dataclass(frozen=True)
class PairedRow:
    """One paired observation on a single trading date."""
    trade_date: date
    symbol_a: str
    symbol_b: str
    expiry_a: date
    expiry_b: date
    expiry_gap_days: int        # signed: a_expiry - b_expiry in days
    px_a: float                 # px_per_gram_999 for leg A
    px_b: float                 # px_per_gram_999 for leg B
    raw_spread: float           # px_a - px_b (no carry adj)
    carry_adj_spread: float     # after carry correction (nan if r_daily unavailable)
    r_daily_used: float         # r_daily used; nan if unavailable / gap==0


# ── expiry matching ───────────────────────────────────────────────────────────

def pair_expiries(
    expiries_a: list[date],
    expiries_b: list[date],
    *,
    max_gap_days: int = 10,
) -> list[ExpiryPair]:
    """Match each expiry in *expiries_a* with the nearest expiry in *expiries_b*.

    Each expiry in A is matched to the single closest expiry in B (by |gap|).
    Multiple expiries in A can map to the same expiry in B (many-to-one is
    allowed; the signal layer should de-duplicate as needed).

    Pairs where |expiry_gap_days| > *max_gap_days* are **excluded**.

    Parameters
    ----------
    expiries_a, expiries_b:
        Lists of expiry dates for symbol A and symbol B respectively.
        Duplicates are silently de-duplicated before matching.
    max_gap_days:
        Maximum |gap| in calendar days to accept.  Default 10.

    Returns
    -------
    List of :class:`ExpiryPair`, one per accepted expiry in A.
    """
    if not expiries_a or not expiries_b:
        return []

    unique_a = sorted(set(expiries_a))
    sorted_b = sorted(set(expiries_b))

    pairs: list[ExpiryPair] = []
    for exp_a in unique_a:
        # find nearest in B
        best_b = min(sorted_b, key=lambda b: abs((exp_a - b).days))
        gap = (exp_a - best_b).days
        if abs(gap) > max_gap_days:
            logger.debug(
                "pair_expiries: rejected (%s, %s) — gap %d days > max %d",
                exp_a, best_b, gap, max_gap_days,
            )
            continue
        pairs.append(ExpiryPair(expiry_a=exp_a, expiry_b=best_b, expiry_gap_days=gap))

    return pairs


# ── carry estimation ──────────────────────────────────────────────────────────

def estimate_r_daily(
    prices: pd.Series,
    days_to_expiry: pd.Series,
    *,
    min_points: int = 5,
) -> float:
    """Estimate daily carry rate from a single symbol's term structure.

    Uses a simple log-linear regression of normalised price on days-to-expiry
    for all live contracts **on the same date** (data must already be filtered
    to a single date by the caller).

        log(px) ≈ log(spot) + r_daily * days_to_expiry

    Parameters
    ----------
    prices:
        px_per_gram_999 for each live expiry on the date.
    days_to_expiry:
        Calendar days until expiry for each row (must be > 0).
    min_points:
        Minimum number of data points required to fit.  Returns ``nan`` if
        fewer points are available.

    Returns
    -------
    Estimated daily carry rate ``r_daily``, or ``float("nan")`` if the
    regression is unstable or there are too few points.

    Notes
    -----
    *No look-ahead.*  The caller must pass only rows with date <= as_of_date.
    """
    mask = (prices > 0) & (days_to_expiry > 0)
    px_clean = prices[mask]
    dte_clean = days_to_expiry[mask]

    if len(px_clean) < min_points:
        logger.debug(
            "estimate_r_daily: only %d valid points (need %d), returning nan",
            len(px_clean), min_points,
        )
        return float("nan")

    log_px = px_clean.apply(math.log)

    # OLS: log_px = intercept + r_daily * dte
    n = len(dte_clean)
    sum_x = dte_clean.sum()
    sum_y = log_px.sum()
    sum_xx = (dte_clean ** 2).sum()
    sum_xy = (dte_clean * log_px).sum()
    denom = n * sum_xx - sum_x ** 2
    if abs(denom) < 1e-12:
        logger.debug("estimate_r_daily: near-singular system, returning nan")
        return float("nan")

    r_daily = (n * sum_xy - sum_x * sum_y) / denom
    return float(r_daily)


# ── carry adjustment ──────────────────────────────────────────────────────────

def carry_adjust(
    px_a: float,
    px_b: float,
    expiry_gap_days_signed: int,
    r_daily: float,
) -> float:
    """Return carry-adjusted spread = px_a − px_b × (1 + r_daily × gap).

    If ``r_daily`` is ``nan`` (estimation failed) or ``expiry_gap_days_signed``
    is 0, returns the raw spread ``px_a − px_b``.

    Parameters
    ----------
    px_a, px_b:
        Normalised prices (px_per_gram_999).
    expiry_gap_days_signed:
        ``expiry_a − expiry_b`` in calendar days (positive means A later).
    r_daily:
        Daily carry rate from :func:`estimate_r_daily`.

    Returns
    -------
    Carry-adjusted spread as a float.
    """
    if expiry_gap_days_signed == 0 or math.isnan(r_daily):
        return px_a - px_b
    return px_a - px_b * (1.0 + r_daily * expiry_gap_days_signed)


# ── high-level builder ────────────────────────────────────────────────────────

def build_pairs_df(
    norm_df: pd.DataFrame,
    symbol_a: str,
    symbol_b: str,
    *,
    carry_symbol: str | None = None,
    max_gap_days: int = 10,
    min_carry_points: int = 5,
    date_col: str = "date",
    symbol_col: str = "symbol",
    expiry_col: str = "expiry_date",
    px_col: str = "px_per_gram_999",
) -> pd.DataFrame:
    """Build a daily paired-spread DataFrame for the (symbol_a, symbol_b) pair.

    For each trading date:
      1. Find all live expiries for A and B.
      2. Match them with :func:`pair_expiries` (nearest-expiry rule).
      3. Estimate ``r_daily`` from *carry_symbol*'s term structure on that date
         (default: symbol_b).
      4. Compute raw and carry-adjusted spreads.

    **No look-ahead:** carry estimation uses only rows on the exact trade date
    (intra-day term structure), not future dates.

    Parameters
    ----------
    norm_df:
        Normalised price DataFrame with at least columns:
        ``date``, ``symbol``, ``expiry_date``, ``px_per_gram_999``.
        The ``date`` column must contain ``datetime.date`` objects (not strings).
    symbol_a, symbol_b:
        Ticker strings (must match the ``symbol`` column exactly after stripping).
    carry_symbol:
        Which symbol to use for carry estimation.  Defaults to *symbol_b*.
    max_gap_days:
        Passed to :func:`pair_expiries`.
    min_carry_points:
        Passed to :func:`estimate_r_daily`.

    Returns
    -------
    DataFrame with one row per (date, expiry_a, expiry_b) triple, columns::

        trade_date, symbol_a, symbol_b,
        expiry_a, expiry_b, expiry_gap_days,
        px_a, px_b,
        raw_spread, carry_adj_spread, r_daily_used
    """
    carry_sym = carry_symbol or symbol_b

    # filter to the two symbols of interest
    mask_a = norm_df[symbol_col].str.strip() == symbol_a
    mask_b = norm_df[symbol_col].str.strip() == symbol_b
    mask_carry = norm_df[symbol_col].str.strip() == carry_sym
    df_a = norm_df[mask_a].copy()
    df_b = norm_df[mask_b].copy()
    df_carry = norm_df[mask_carry].copy()

    if df_a.empty or df_b.empty:
        logger.warning(
            "build_pairs_df: no rows for %r or %r — returning empty DataFrame",
            symbol_a, symbol_b,
        )
        return pd.DataFrame(columns=[
            "trade_date", "symbol_a", "symbol_b",
            "expiry_a", "expiry_b", "expiry_gap_days",
            "px_a", "px_b", "raw_spread", "carry_adj_spread", "r_daily_used",
        ])

    all_dates = sorted(set(df_a[date_col]) & set(df_b[date_col]))
    rows: list[dict] = []

    for trade_date in all_dates:
        slice_a = df_a[df_a[date_col] == trade_date]
        slice_b = df_b[df_b[date_col] == trade_date]
        slice_carry = df_carry[df_carry[date_col] == trade_date]

        expiries_a = slice_a[expiry_col].tolist()
        expiries_b = slice_b[expiry_col].tolist()

        matched = pair_expiries(expiries_a, expiries_b, max_gap_days=max_gap_days)
        if not matched:
            continue

        # estimate r_daily from carry symbol's term structure on this date
        if not slice_carry.empty and expiry_col in slice_carry.columns:
            dte = (slice_carry[expiry_col] - trade_date).apply(lambda d: d.days)
            r_daily = estimate_r_daily(
                slice_carry[px_col].reset_index(drop=True),
                dte.reset_index(drop=True),
                min_points=min_carry_points,
            )
        else:
            r_daily = float("nan")

        # look up px for each matched pair
        px_map_a = slice_a.set_index(expiry_col)[px_col].to_dict()
        px_map_b = slice_b.set_index(expiry_col)[px_col].to_dict()

        for ep in matched:
            px_a = px_map_a.get(ep.expiry_a)
            px_b = px_map_b.get(ep.expiry_b)
            if px_a is None or px_b is None:
                continue

            raw = px_a - px_b
            adj = carry_adjust(px_a, px_b, ep.expiry_gap_days, r_daily)

            rows.append({
                "trade_date": trade_date,
                "symbol_a": symbol_a,
                "symbol_b": symbol_b,
                "expiry_a": ep.expiry_a,
                "expiry_b": ep.expiry_b,
                "expiry_gap_days": ep.expiry_gap_days,
                "px_a": px_a,
                "px_b": px_b,
                "raw_spread": raw,
                "carry_adj_spread": adj,
                "r_daily_used": r_daily,
            })

    return pd.DataFrame(rows)
