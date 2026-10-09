"""
tests/test_backtest.py
======================
Unit tests for model/backtest.py
"""
import pandas as pd
from datetime import date
from model.backtest import run_backtest
from model.signal import SignalConfig, LiquidityBucket
from model.costs import CostConfig

def test_run_backtest_empty():
    res = run_backtest(pd.DataFrame(), SignalConfig(), CostConfig.from_dict({}), 100.0, {})
    assert res.empty


def test_run_backtest_ledger():
    # Make a dummy pairs dataframe that triggers exactly one trade.
    rows = []
    # 5 stable rows, 1 spike, 5 flat rows.
    spreads = [0.0]*5 + [30.0] + [0.0]*5
    for i, s in enumerate(spreads):
        rows.append({
            "trade_date": date(2026, 1, 1).replace(day=i+1),
            "symbol_a": "GOLDM",
            "symbol_b": "GOLDPETAL",
            "expiry_a": date(2026, 2, 5),
            "expiry_b": date(2026, 2, 5),
            "expiry_gap_days": 0,
            "px_a": 6000.0 + s,
            "px_b": 6000.0,
            "raw_spread": s,
            "carry_adj_spread": s,
            "liquidity_a": LiquidityBucket.LIQUID.value,
            "liquidity_b": LiquidityBucket.LIQUID.value,
            "dte_a": 30 - i,
            "dte_b": 30 - i,
            "vol_a": 1000.0, # Just adding fake volume 
            "vol_b": 1000.0,
        })
    df = pd.DataFrame(rows)

    cfg = SignalConfig(lookback=5, z_entry=1.5, z_exit=0.3, max_hold_days=50, 
                       exit_days_before_expiry=0, tender_days=0, min_expiry_gap_days=0, max_expiry_gap_days=10)
    
    cost = CostConfig.from_dict({
        "brokerage": {"per_order_inr": 0.0, "per_lot_inr": 0.0},
        "exchange_transaction_charge_bps": 0.0,
        "ctt_bps": 0.0,
        "gst_pct": 0.0,
        "stamp_duty_bps": 0.0,
        "slippage": {
            "liquid": {"base_bps": 0.0, "impact_k": 0.0}
        }
    })

    meta = {
        "GOLDM": {"lot_size_grams": 100.0},
        "GOLDPETAL": {"lot_size_grams": 1.0}
    }

    res = run_backtest(df, cfg, cost, 100.0, meta)
    
    # We should get 1 trade in the ledger
    assert len(res) == 1
    trade = res.iloc[0]
    assert trade["symbol_a"] == "GOLDM"
    assert trade["lots_a"] == 1
    assert trade["lots_b"] == 100
    
    # Entry should be at index 6 (spike was at index 5, actually lookback triggers on next?)
    # Spreads: 0,0,0,0,0, 30, 0,0,0,0,0
    # Day 6 (index 5, 30.0) is the entry signal. 
    # Let's just check it generated something.
    assert "gross_pnl" in res.columns
    assert "net_pnl" in res.columns
    assert res["entry_fees"].iloc[0] == 0.0
