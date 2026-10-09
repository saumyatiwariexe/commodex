"""
model/backtest.py
=================
Core backtest loop coordinating pairing, signal generation, sizing, and costs.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List
import pandas as pd

from model.signal import SignalConfig, generate_signals
from model.costs import CostConfig, compute_slippage_bps, compute_fill_costs
from model.sizing import match_lots, hedge_residual

logger = logging.getLogger(__name__)

def run_backtest(
    pairs_df: pd.DataFrame,
    signal_cfg: SignalConfig,
    cost_cfg: CostConfig,
    target_grams_per_leg: float,
    contracts_meta: Dict[str, Any],
) -> pd.DataFrame:
    """Run the backtest loop over a pre-paired DataFrame.

    Parameters
    ----------
    pairs_df : pd.DataFrame
        Output of `model.pairing.build_pairs_df`
    signal_cfg : SignalConfig
    cost_cfg : CostConfig
    target_grams_per_leg : float
        Target notional size in grams.
    contracts_meta : dict
        Mapping of symbol -> metadata (must include lot_size_grams).

    Returns
    -------
    pd.DataFrame
        Trade ledger containing entry/exit details, sizes, fees, and PnL.
    """
    if pairs_df.empty:
        return pd.DataFrame()

    # 1. Generate signals
    df = generate_signals(pairs_df, signal_cfg)

    ledger = []
    
    # We iterate over the dataframe. We look for rows where position_state != 'flat'.
    # A continuous block of position_state == 'long_a' or 'long_b' represents one trade.
    
    in_position = False
    current_trade: Dict[str, Any] = {}

    for i, row in df.iterrows():
        state = row["position_state"]
        
        if not in_position and state != "flat":
            # ENTRY
            in_position = True
            is_long_a = (state == "long_a")
            
            # Sizing
            sym_a = row["symbol_a"]
            sym_b = row["symbol_b"]
            lots_a, lots_b = match_lots(
                target_grams_per_leg,
                contracts_meta[sym_a]["lot_size_grams"],
                contracts_meta[sym_b]["lot_size_grams"]
            )
            
            current_trade = {
                "entry_date": row["trade_date"],
                "symbol_a": sym_a,
                "symbol_b": sym_b,
                "expiry_a": row["expiry_a"],
                "expiry_b": row["expiry_b"],
                "direction": state,
                "lots_a": lots_a,
                "lots_b": lots_b,
                "residual_grams": hedge_residual(
                    lots_a, contracts_meta[sym_a]["lot_size_grams"],
                    lots_b, contracts_meta[sym_b]["lot_size_grams"]
                )
            }
            
            # Costs A
            side_a = "BUY" if is_long_a else "SELL"
            # We don't have avg_daily_vol in pairs_df, assume perfectly liquid for now or 0
            # To do this perfectly we'd need trailing volume. 
            slip_bps_a = compute_slippage_bps(cost_cfg, row["liquidity_a"], 
                                              lots_a * contracts_meta[sym_a]["lot_size_grams"], 1000000.0)
            px_a, fees_a = compute_fill_costs(cost_cfg, side_a, lots_a, row["px_a"], 
                                              contracts_meta[sym_a]["lot_size_grams"], slip_bps_a)
            
            # Costs B
            side_b = "SELL" if is_long_a else "BUY"
            slip_bps_b = compute_slippage_bps(cost_cfg, row["liquidity_b"], 
                                              lots_b * contracts_meta[sym_b]["lot_size_grams"], 1000000.0)
            px_b, fees_b = compute_fill_costs(cost_cfg, side_b, lots_b, row["px_b"], 
                                              contracts_meta[sym_b]["lot_size_grams"], slip_bps_b)
            
            current_trade["entry_px_a"] = px_a
            current_trade["entry_px_b"] = px_b
            current_trade["entry_fees"] = fees_a + fees_b
            current_trade["entry_z"] = row["z_score"]

        elif in_position and state == "flat":
            # EXIT
            in_position = False
            is_long_a = (current_trade["direction"] == "long_a")
            sym_a = current_trade["symbol_a"]
            sym_b = current_trade["symbol_b"]
            lots_a = current_trade["lots_a"]
            lots_b = current_trade["lots_b"]
            
            # Costs A (opposite side)
            side_a = "SELL" if is_long_a else "BUY"
            slip_bps_a = compute_slippage_bps(cost_cfg, row["liquidity_a"], 
                                              lots_a * contracts_meta[sym_a]["lot_size_grams"], 1000000.0)
            px_a, fees_a = compute_fill_costs(cost_cfg, side_a, lots_a, row["px_a"], 
                                              contracts_meta[sym_a]["lot_size_grams"], slip_bps_a)
                                              
            # Costs B
            side_b = "BUY" if is_long_a else "SELL"
            slip_bps_b = compute_slippage_bps(cost_cfg, row["liquidity_b"], 
                                              lots_b * contracts_meta[sym_b]["lot_size_grams"], 1000000.0)
            px_b, fees_b = compute_fill_costs(cost_cfg, side_b, lots_b, row["px_b"], 
                                              contracts_meta[sym_b]["lot_size_grams"], slip_bps_b)
            
            current_trade["exit_date"] = row["trade_date"]
            current_trade["exit_px_a"] = px_a
            current_trade["exit_px_b"] = px_b
            current_trade["exit_fees"] = fees_a + fees_b
            current_trade["exit_reason"] = row["exit_reason"]
            current_trade["hold_days"] = row["hold_days"]
            
            # PnL
            # For A: (exit - entry) * lots * unit_size IF long, else (entry - exit)
            pnl_a = (px_a - current_trade["entry_px_a"]) * lots_a * contracts_meta[sym_a]["lot_size_grams"]
            if not is_long_a: pnl_a = -pnl_a
            
            pnl_b = (px_b - current_trade["entry_px_b"]) * lots_b * contracts_meta[sym_b]["lot_size_grams"]
            if is_long_a: pnl_b = -pnl_b
            
            current_trade["gross_pnl"] = pnl_a + pnl_b
            current_trade["net_pnl"] = current_trade["gross_pnl"] - current_trade["entry_fees"] - current_trade["exit_fees"]
            
            ledger.append(current_trade)
            current_trade = {}

    return pd.DataFrame(ledger)
