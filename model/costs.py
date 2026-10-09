"""
model/costs.py
==============
Trading cost calculation (MODEL.md §6).

Fills are priced at settlement. A "slippage haircut" accounts for the fact
that one cannot usually execute exactly at settlement.

All cost parameters must be loaded from `costs.yaml`. Do not hard-code rates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class LiquidityCostConfig:
    base_bps: float
    impact_k: float


@dataclass(frozen=True)
class CostConfig:
    brokerage_per_order_inr: float
    brokerage_per_lot_inr: float
    exchange_transaction_charge_bps: float
    ctt_bps: float
    gst_pct: float
    stamp_duty_bps: float

    slippage_liquid: LiquidityCostConfig
    slippage_normal: LiquidityCostConfig
    slippage_thin: LiquidityCostConfig

    @classmethod
    def from_dict(cls, data: dict) -> "CostConfig":
        """Load from a parsed YAML dictionary."""
        # Fall back to 0.0 for placeholders (null) so tests/runs don't crash,
        # but in production these should be validated.
        def _f(val: Optional[float]) -> float:
            return float(val) if val is not None else 0.0

        b = data.get("brokerage", {})
        s = data.get("slippage", {})

        return cls(
            brokerage_per_order_inr=_f(b.get("per_order_inr")),
            brokerage_per_lot_inr=_f(b.get("per_lot_inr")),
            exchange_transaction_charge_bps=_f(data.get("exchange_transaction_charge_bps")),
            ctt_bps=_f(data.get("ctt_bps")),
            gst_pct=_f(data.get("gst_pct", 18.0)),
            stamp_duty_bps=_f(data.get("stamp_duty_bps")),
            slippage_liquid=LiquidityCostConfig(
                base_bps=_f(s.get("liquid", {}).get("base_bps")),
                impact_k=_f(s.get("liquid", {}).get("impact_k")),
            ),
            slippage_normal=LiquidityCostConfig(
                base_bps=_f(s.get("normal", {}).get("base_bps")),
                impact_k=_f(s.get("normal", {}).get("impact_k")),
            ),
            slippage_thin=LiquidityCostConfig(
                base_bps=_f(s.get("thin", {}).get("base_bps")),
                impact_k=_f(s.get("thin", {}).get("impact_k")),
            ),
        )


def compute_slippage_bps(
    cfg: CostConfig,
    liquidity_bucket: str,
    order_grams: float,
    avg_daily_vol_grams: float,
) -> float:
    """Calculate slippage in basis points based on liquidity and order size."""
    if liquidity_bucket == "liquid":
        liq_cfg = cfg.slippage_liquid
    elif liquidity_bucket == "thin":
        liq_cfg = cfg.slippage_thin
    else:
        liq_cfg = cfg.slippage_normal

    # Prevent division by zero
    if avg_daily_vol_grams <= 0:
        return liq_cfg.base_bps + liq_cfg.impact_k * 100.0  # arbitrary high penalty

    ratio = order_grams / avg_daily_vol_grams
    return liq_cfg.base_bps + (liq_cfg.impact_k * ratio)


def compute_fill_costs(
    cfg: CostConfig,
    side: str,
    lots: int,
    price_inr: float,
    lot_size_grams: float,
    slippage_bps: float,
) -> tuple[float, float]:
    """Compute the actual fill price (including slippage) and total fees.

    Parameters
    ----------
    cfg: CostConfig
    side: "BUY" or "SELL"
    lots: Number of contracts traded
    price_inr: The raw settlement price in INR for one lot
    lot_size_grams: The size of one lot in grams
    slippage_bps: The slippage to apply

    Returns
    -------
    (executable_price_inr, total_fees_inr)
    The executable price is per lot. total_fees is for the entire order.
    """
    is_buy = (side.upper() == "BUY")

    # 1. Slippage (adverse to trader)
    # 1 bps = 0.0001
    slip_factor = (slippage_bps / 10000.0)
    if is_buy:
        exec_price = price_inr * (1.0 + slip_factor)
    else:
        exec_price = price_inr * (1.0 - slip_factor)

    turnover = exec_price * lots

    # 2. Fees
    brokerage = cfg.brokerage_per_order_inr + (cfg.brokerage_per_lot_inr * lots)
    exchange_charges = turnover * (cfg.exchange_transaction_charge_bps / 10000.0)

    # CTT only applies on the sell side for non-agricultural commodities
    ctt = turnover * (cfg.ctt_bps / 10000.0) if not is_buy else 0.0

    gst = (brokerage + exchange_charges) * (cfg.gst_pct / 100.0)

    # Stamp duty only applies on the buy side
    stamp_duty = turnover * (cfg.stamp_duty_bps / 10000.0) if is_buy else 0.0

    total_fees = brokerage + exchange_charges + ctt + gst + stamp_duty

    return exec_price, total_fees
