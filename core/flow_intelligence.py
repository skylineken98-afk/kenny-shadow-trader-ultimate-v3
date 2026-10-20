"""Directional volume/money-flow proxies. Not institutional order-flow or valuation feeds.

Uses OHLCV only. Trade-side, dark-pool, options sweeps and exact net flows
cannot be established from these candles.
"""
import math
import pandas as pd


def _finite(x):
    try:
        f = float(x)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def measure_flow(candles, window=20):
    """Return interpretable flow statistics; None when data inadequate."""
    if candles is None or len(candles) < window + 2:
        return None
    needed = ['High', 'Low', 'Close', 'Volume']
    if any(c not in candles for c in needed):
        return None
    d = candles[needed].apply(pd.to_numeric, errors='coerce').dropna()
    if len(d) < window + 2 or (d['Volume'] < 0).any():
        return None
    high, low, close, vol = [d[c].astype(float) for c in needed]
    baseline = vol.iloc[-window-1:-1].mean()
    lastvol = _finite(vol.iloc[-1])
    if baseline <= 0 or lastvol is None:
        return None
    rvol = lastvol / baseline
    typical = (high + low + close) / 3
    signed_flow = typical.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0)) * typical * vol
    latest = signed_flow.tail(window)
    positive = float(latest[latest > 0].sum())
    negative = float(-latest[latest < 0].sum())
    mfi_denom = positive + negative
    mfi = 50 if mfi_denom == 0 else 100 * positive / mfi_denom
    span = (high - low).where((high-low) != 0)
    clv = (((close-low)-(high-close)) / span).fillna(0).clip(-1,1)
    cmf = float((clv*vol).tail(window).sum() / vol.tail(window).sum()) if vol.tail(window).sum()>0 else 0.
    avg_dollar_vol = float((close*vol).iloc[-window-1:-1].mean())
    price_change = float(close.iloc[-1] / close.iloc[-window-1]-1) if close.iloc[-window-1] > 0 else 0
    direction = ('BULLISH' if cmf >= 0.10 and mfi >= 55 and price_change > 0 else
                 'BEARISH' if cmf <= -0.10 and mfi <= 45 and price_change < 0 else 'MIXED')
    return {'direction':direction,'relative_volume':round(rvol,2),
            'chaikin_money_flow':round(cmf,3),'money_flow_index_proxy':round(mfi,1),
            'avg_dollar_volume':round(avg_dollar_vol,2),
            'lookback_return_pct':round(price_change*100,2),
            'evidence':'OHLCV-based pressure proxy; not verified institutional buying/selling'}


def alignment_bonus(flow, direction):
    """Small capped score adjustment; liquidity/chain scores remain essential."""
    if not flow or flow.get('direction') != direction:
        return 0.
    rvol = _finite(flow.get('relative_volume')) or 0
    cmf = _finite(flow.get('chaikin_money_flow')) or 0
    return round(min(8., max(0., (rvol-1)*3) + min(abs(cmf)*12, 4)),2)
