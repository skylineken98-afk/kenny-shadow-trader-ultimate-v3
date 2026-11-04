"""SPX scalping research diagnostics. OHLCV proxies are NOT real order flow.

All inputs must be chronological, completed 1-minute candles; the caller is
responsible for excluding an actively forming candle. This module never trades.
"""
import math
import pandas as pd


def volume_profile_proxy(bars: pd.DataFrame, bins: int = 32, lookback: int = 1170):
    """Approximate a 3-session volume-by-price histogram from candle typical prices.

    Candle volume is assigned to ONE price bin; this is not tick-level or
    exchange volume-at-price. SPX index volume may be empty; use SPY as a
    clearly labeled proxy if appropriate. Returns POC and 70% value area.
    """
    if not 8 <= bins <= 200:
        raise ValueError('bins must be in [8, 200]')
    if not isinstance(bars, pd.DataFrame) or not {'High','Low','Close','Volume'}.issubset(bars):
        return None
    d = bars[['High','Low','Close','Volume']].apply(pd.to_numeric,errors='coerce').tail(lookback)
    if len(d) < 20 or d.isna().any().any():
        return None
    vals=d.to_numpy(dtype=float)
    if not all(math.isfinite(v) for row in vals for v in row):
        return None
    if (d['Volume'] < 0).any() or float(d['Volume'].sum()) <= 0:
        return None
    if (d['High'] < d['Low']).any():
        return None
    low,high=float(d['Low'].min()),float(d['High'].max())
    if high <= low:
        return None
    typical=(d['High']+d['Low']+d['Close'])/3.0
    step=(high-low)/bins
    hist=[0.0]*bins
    for price,volume in zip(typical,d['Volume']):
        slot=min(bins-1,max(0,int((float(price)-low)/step)))
        hist[slot]+=float(volume)
    poc=max(range(bins),key=hist.__getitem__)
    left=right=poc
    included=hist[poc]
    threshold=0.70*sum(hist)
    while included < threshold and (left>0 or right<bins-1):
        lvol=hist[left-1] if left>0 else -1
        rvol=hist[right+1] if right<bins-1 else -1
        if rvol>lvol:
            right+=1;included+=hist[right]
        else:
            left-=1;included+=hist[left]
    return {'poc':round(low+(poc+0.5)*step,4),
            'value_area_low':round(low+left*step,4),
            'value_area_high':round(low+(right+1)*step,4),
            'histogram':[{'price':round(low+(i+0.5)*step,4),'volume':round(x,2)} for i,x in enumerate(hist)],
            'source':'OHLCV candle typical-price allocation (approximation, not footprint)'}


def pressure_proxy(bars: pd.DataFrame, window: int = 20):
    """Candle close-location volume pressure; NOT bid/ask volume delta."""
    if not isinstance(bars,pd.DataFrame) or len(bars)<window or not {'High','Low','Close','Volume'}.issubset(bars):
        return None
    d=bars[['High','Low','Close','Volume']].apply(pd.to_numeric,errors='coerce').tail(window)
    if d.isna().any().any() or (d.Volume<0).any() or float(d.Volume.sum())<=0:
        return None
    span=(d.High-d.Low)
    if (span<0).any(): return None
    clv=((2*d.Close-d.High-d.Low)/span.where(span>0)).fillna(0).clip(-1,1)
    pressure=float((clv*d.Volume).sum()/d.Volume.sum())
    return {'close_location_pressure':round(pressure,4),
            'estimated_positive_volume':round(float(((clv+1)*.5*d.Volume).sum()),2),
            'estimated_negative_volume':round(float(((1-clv)*.5*d.Volume).sum()),2),
            'interpretation':'buyer-leaning' if pressure>0.15 else 'seller-leaning' if pressure<-.15 else 'mixed',
            'source':'Candle-derived pressure, NOT real bid/ask delta, dark pools or options flow'}
