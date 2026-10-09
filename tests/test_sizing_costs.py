"""
tests/test_sizing_costs.py
==========================
Unit tests for model/sizing.py and model/costs.py
"""
import pytest
from model.sizing import match_lots, hedge_residual
from model.costs import (
    CostConfig,
    LiquidityCostConfig,
    compute_slippage_bps,
    compute_fill_costs,
)


def test_match_lots_exact():
    # 100g target, unit A = 10g, unit B = 1g
    lots_a, lots_b = match_lots(100.0, 10.0, 1.0)
    assert lots_a == 10
    assert lots_b == 100

def test_match_lots_rounding():
    # 100g target, unit A = 8g (Guinea), unit B = 1g
    # 100 / 8 = 12.5 -> rounds to 12 or 13 depending on python round (12 in python 3 due to bankers rounding)
    lots_a, lots_b = match_lots(100.0, 8.0, 1.0)
    assert lots_a == 12
    assert lots_b == 100

def test_match_lots_minimum_1():
    # 1g target, unit A = 100g. 1/100 = 0.01 -> 0, but bumped to 1.
    lots_a, lots_b = match_lots(1.0, 100.0, 1.0)
    assert lots_a == 1
    assert lots_b == 1

def test_hedge_residual():
    # Long 12 Guinea (8g) = 96g. Short 100 Petal (1g) = 100g. Net = -4g.
    res = hedge_residual(12, 8.0, 100, 1.0)
    assert res == -4.0


def test_cost_config_from_dict():
    data = {
        "brokerage": {"per_order_inr": 20.0, "per_lot_inr": 0.0},
        "exchange_transaction_charge_bps": 2.6,
        "ctt_bps": 10.0,
        "gst_pct": 18.0,
        "stamp_duty_bps": 0.2,
        "slippage": {
            "liquid": {"base_bps": 1.0, "impact_k": 0.5},
            "normal": {"base_bps": 3.0, "impact_k": 1.0},
            "thin": {"base_bps": 10.0, "impact_k": 5.0},
        }
    }
    cfg = CostConfig.from_dict(data)
    assert cfg.brokerage_per_order_inr == 20.0
    assert cfg.ctt_bps == 10.0
    assert cfg.slippage_liquid.base_bps == 1.0


def test_compute_slippage_bps():
    cfg = CostConfig.from_dict({
        "slippage": {
            "liquid": {"base_bps": 1.0, "impact_k": 0.5},
            "normal": {"base_bps": 3.0, "impact_k": 1.0},
            "thin": {"base_bps": 10.0, "impact_k": 5.0},
        }
    })
    
    # liquid, size=10g, avg=1000g -> ratio=0.01. slip = 1.0 + (0.5 * 0.01) = 1.005
    slip = compute_slippage_bps(cfg, "liquid", 10.0, 1000.0)
    assert abs(slip - 1.005) < 1e-9

    # zero volume handling
    slip = compute_slippage_bps(cfg, "thin", 10.0, 0.0)
    assert slip == 510.0  # 10 + 5.0 * 100


def test_compute_fill_costs():
    cfg = CostConfig.from_dict({
        "brokerage": {"per_order_inr": 20.0, "per_lot_inr": 0.0},
        "exchange_transaction_charge_bps": 2.0, # 0.0002
        "ctt_bps": 10.0,                        # 0.001
        "gst_pct": 18.0,
        "stamp_duty_bps": 0.5,                  # 0.00005
        "slippage": {}
    })
    
    # BUY 1 lot at 10,000 with 5 bps slippage (5 bps = 0.0005 * 10000 = 5 rupees slippage)
    # Exec price = 10005
    # Turnover = 10005
    # Brokerage = 20
    # Exchange = 10005 * 0.0002 = 2.001
    # CTT = 0 (buy side)
    # Stamp duty = 10005 * 0.00005 = 0.50025
    # GST = (20 + 2.001) * 0.18 = 3.96018
    # Total fees = 20 + 2.001 + 0 + 3.96018 + 0.50025 = 26.46143
    
    exec_px, fees = compute_fill_costs(cfg, "BUY", 1, 10000.0, 1.0, 5.0)
    assert exec_px == 10005.0
    assert abs(fees - 26.46143) < 1e-5

    # SELL side -> no stamp duty, yes CTT. 
    # Slippage is negative (sell lower). 10000 -> 9995
    # Turnover = 9995
    # Brokerage = 20
    # Exchange = 9995 * 0.0002 = 1.999
    # CTT = 9995 * 0.001 = 9.995
    # Stamp duty = 0
    # GST = (20 + 1.999) * 0.18 = 3.95982
    # Total fees = 20 + 1.999 + 9.995 + 3.95982 + 0 = 35.95382
    exec_px, fees = compute_fill_costs(cfg, "SELL", 1, 10000.0, 1.0, 5.0)
    assert exec_px == 9995.0
    assert abs(fees - 35.95382) < 1e-5
