import pandas as pd
import numpy as np
from datetime import date
from model.attribution import compute_daily_equity, compute_attribution

def test_compute_daily_equity_empty():
    ledger = pd.DataFrame()
    daily = compute_daily_equity(ledger, 100000.0, date(2026, 1, 1), date(2026, 1, 10))
    assert len(daily) > 0
    assert (daily["daily_pnl"] == 0).all()
    assert (daily["equity"] == 100000.0).all()

def test_compute_daily_equity_straight_line():
    ledger = pd.DataFrame([{
        "entry_date": pd.Timestamp("2026-01-01"),
        "exit_date": pd.Timestamp("2026-01-05"), # 3 business days: 1st(Thu), 2nd(Fri), 5th(Mon)
        "net_pnl": 300.0
    }])
    
    daily = compute_daily_equity(ledger, 10000.0, date(2026, 1, 1), date(2026, 1, 10))
    # It should distribute 100 per day on Jan 1, 2, 5
    daily = daily.set_index("date")
    assert daily.loc[pd.Timestamp("2026-01-01")]["daily_pnl"] == 100.0
    assert daily.loc[pd.Timestamp("2026-01-02")]["daily_pnl"] == 100.0
    assert daily.loc[pd.Timestamp("2026-01-05")]["daily_pnl"] == 100.0
    assert daily.loc[pd.Timestamp("2026-01-06")]["daily_pnl"] == 0.0
    
    assert daily.loc[pd.Timestamp("2026-01-09")]["cum_pnl"] == 300.0

def test_compute_attribution():
    dates = pd.date_range("2026-01-01", "2026-12-31", freq="B")
    
    # Create artificial returns
    # benchmark ~ N(0, 1)
    # strategy = 0.5 * benchmark + 0.001 + noise
    np.random.seed(42)
    bench_returns = pd.Series(np.random.normal(0, 0.01, len(dates)), index=dates)
    strat_returns = 0.5 * bench_returns + 0.001 + np.random.normal(0, 0.005, len(dates))
    
    attr = compute_attribution(strat_returns, bench_returns)
    
    assert np.isclose(attr["beta"], 0.5, atol=0.1)
    assert np.isclose(attr["alpha_ann"], 0.001 * 252, atol=0.1)
    assert 0 < attr["r_squared"] < 1.0

def test_compute_attribution_zero_var():
    bench = pd.Series([0.0]*10)
    strat = pd.Series([0.01]*10)
    attr = compute_attribution(strat, bench)
    assert attr["beta"] == 0.0
    assert attr["alpha_ann"] == 0.0
