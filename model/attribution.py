import pandas as pd
import numpy as np
from typing import Dict, Any

def compute_daily_equity(ledger: pd.DataFrame, target_notional_inr: float, start_date, end_date) -> pd.DataFrame:
    """
    Convert a trade ledger into a daily equity curve.
    Uses target_notional_inr as the constant denominator to compute daily returns.
    """
    if ledger.empty:
        idx = pd.date_range(start_date, end_date, freq="B")
        return pd.DataFrame({
            "date": idx,
            "daily_pnl": 0.0,
            "cum_pnl": 0.0,
            "daily_return": 0.0,
            "equity": target_notional_inr
        }).set_index("date")
        
    # We will spread the PnL evenly over the hold days, or just book it on exit.
    # For a true daily equity curve, we should ideally mark-to-market daily.
    # Since we only have trade entry/exit in the ledger, we'll do a simple straight-line 
    # daily PnL interpolation between entry and exit.
    
    dates = pd.date_range(start_date, end_date, freq="B")
    daily = pd.DataFrame(index=dates, columns=["daily_pnl"]).fillna(0.0)
    
    for _, trade in ledger.iterrows():
        # If exit_date is missing, it's still open; we skip or mark to last date
        if pd.isnull(trade.get("exit_date")):
            continue
            
        entry = trade["entry_date"]
        exit = trade["exit_date"]
        net_pnl = trade["net_pnl"]
        
        trade_dates = pd.date_range(entry, exit, freq="B")
        days = len(trade_dates)
        if days > 0:
            daily_pnl = net_pnl / days
            for d in trade_dates:
                if d in daily.index:
                    daily.loc[d, "daily_pnl"] += daily_pnl
                    
    daily["cum_pnl"] = daily["daily_pnl"].cumsum()
    daily["equity"] = target_notional_inr + daily["cum_pnl"]
    daily["daily_return"] = daily["daily_pnl"] / target_notional_inr
    
    return daily.reset_index().rename(columns={"index": "date"})

def compute_attribution(strategy_returns: pd.Series, benchmark_returns: pd.Series) -> Dict[str, float]:
    """
    Compute Alpha, Beta, and R^2 against a benchmark (e.g. Gold).
    """
    # Align the two series
    df = pd.concat([strategy_returns, benchmark_returns], axis=1).dropna()
    df.columns = ["strategy", "benchmark"]
    
    if len(df) < 2 or df["benchmark"].var() == 0:
        return {
            "beta": 0.0,
            "alpha_ann": 0.0,
            "r_squared": 0.0
        }
        
    cov = df.cov().iloc[0, 1]
    var_bench = df["benchmark"].var()
    beta = cov / var_bench
    
    mean_strat = df["strategy"].mean()
    mean_bench = df["benchmark"].mean()
    
    # Alpha = E[R_s] - Beta * E[R_b]
    # Annualized (assuming ~252 business days)
    alpha = mean_strat - beta * mean_bench
    alpha_ann = alpha * 252
    
    # R^2
    corr = df.corr().iloc[0, 1]
    r_squared = corr ** 2
    
    return {
        "beta": float(beta),
        "alpha_ann": float(alpha_ann),
        "r_squared": float(r_squared)
    }
