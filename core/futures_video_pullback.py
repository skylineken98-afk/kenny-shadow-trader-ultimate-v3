"""NQ/MNQ video-inspired trend pullback hypothesis; offline research ONLY.

Uses completed, timezone-aware 5-minute OHLCV bars. A pullback in a
20/50 EMA trend is confirmed by a completed candle breaking the prior
candle high/low. Decisions are recorded on candle close; simulated
entries use the NEXT bar open. No broker imports, calls or orders.
"""
import math
import pandas as pd
from core.strategy_discovery import _bars

SYMBOL_MULTIPLIERS = {"NQ": 20.0, "MNQ": 2.0}
STRATEGY_ID = "nq_mnq_ema_pullback_confirmation_v1"

def _input(bars):
    b = _bars(bars)
    intervals = b.index.to_series().diff().dropna()
    if not (intervals == pd.Timedelta(minutes=5)).all():
        raise ValueError("Only contiguous completed 5-minute candles are supported; split sessions before calling")
    if (b.High < b[['Open','Close','Low']].max(axis=1)).any() or (b.Low > b[['Open','Close']].min(axis=1)).any():
        raise ValueError("Inconsistent OHLC")
    return b

def decisions(bars):
    """Only same-and-earlier completed candles influence each signal."""
    b = _input(bars)
    close = b.Close
    fast = close.ewm(span=20, adjust=False).mean()
    slow = close.ewm(span=50, adjust=False).mean()
    # Previous bar pulls toward the fast EMA while avoiding a trend break.
    long = (fast > slow) & (b.Low.shift(1) <= fast.shift(1)) & (b.Close.shift(1) > slow.shift(1)) & (close > b.High.shift(1)) & (close > b.Open)
    short = (fast < slow) & (b.High.shift(1) >= fast.shift(1)) & (b.Close.shift(1) < slow.shift(1)) & (close < b.Low.shift(1)) & (close < b.Open)
    result = long.astype(int) - short.astype(int)
    result.iloc[:55] = 0
    return result

def backtest(bars, *, symbol="MNQ", contracts=1, holding_bars=3, fee_per_side=1.5, slippage_ticks_per_side=1, tick_size=0.25):
    """Descriptive fixed-hold test; explicit futures point value and costs.

    This intentionally does NOT model stops, targets, margin, fill certainty,
    variable spreads, gaps or session rollovers; never publish as a live edge.
    """
    if symbol not in SYMBOL_MULTIPLIERS:
        raise ValueError("Supported symbols: NQ, MNQ")
    if not isinstance(contracts,int) or not 1 <= contracts <= 20 or not isinstance(holding_bars,int) or not 1 <= holding_bars <= 30:
        raise ValueError("Invalid position size or holding period")
    if any(not math.isfinite(float(x)) or float(x)<0 for x in (fee_per_side,slippage_ticks_per_side)) or not math.isfinite(float(tick_size)) or tick_size <= 0:
        raise ValueError("Invalid costs")
    b = _input(bars)
    d = decisions(b)
    multiplier = SYMBOL_MULTIPLIERS[symbol]
    records = []
    i = 56
    while i + holding_bars < len(b):
        direction = int(d.iloc[i-1])
        if not direction:
            i += 1
            continue
        entry = float(b.Open.iloc[i])
        exit_price = float(b.Open.iloc[i + holding_bars])
        gross_points = direction*(exit_price-entry)
        gross_usd = gross_points * multiplier * contracts
        fees = 2*float(fee_per_side)*contracts
        slippage_usd = 2*float(slippage_ticks_per_side)*tick_size*multiplier*contracts
        records.append({"decision_at":str(b.index[i-1]),"entry_at":str(b.index[i]),
                        "exit_at":str(b.index[i+holding_bars]),"direction":direction,
                        "entry_price":entry,"exit_price":exit_price,
                        "gross_points":gross_points,"net_usd":round(gross_usd-fees-slippage_usd,2)})
        i += holding_bars + 1
    nets = [r["net_usd"] for r in records]
    return {"strategy":STRATEGY_ID,"symbol":symbol,"contracts":contracts,
            "status":"DESCRIPTIVE_SIMULATION","research_only":True,
            "broker_orders_enabled":False,"live_signal_feed_enabled":False,
            "trades":len(nets),"win_rate":sum(v>0 for v in nets)/len(nets) if nets else None,
            "net_total_usd":round(sum(nets),2),"records":records,
            "limitations":"Fixed hold, synthetic next-open fills, no exchange calendar, stop, target or gap modeling."}
