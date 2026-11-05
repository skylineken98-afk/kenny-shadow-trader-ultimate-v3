"""Evidence-based momentum decision research. Never routes live orders.

Uses confirmed closed candles; small lookback intentionally avoids lookahead.
No promise that today's strongest mover keeps moving.
"""
from math import isfinite

def number(x):
    try:
        v=float(x)
        return v if isfinite(v) else None
    except (ValueError,TypeError,OverflowError):return None

def momentum_decision(symbol,bars,*,min_bars=8):
    """Return a candidate for a PAPER strategy, not a broker instruction.

    Bars must be chronological, completed, and contain c,h,l,v and timestamp.
    Momentum requires aligned 3/8-bar trend, expanding participation and a
    confirmed close through the previous short range. Missing data => no trade.
    """
    if not isinstance(bars,list) or len(bars)<min_bars:return {"symbol":symbol,"action":"NO_TRADE","reason":"Insufficient completed candles"}
    recent=bars[-min_bars:]
    candles=[]
    last_stamp=None
    for b in recent:
        if not b.get("complete",False):return {"symbol":symbol,"action":"NO_TRADE","reason":"Unconfirmed candle"}
        try:
            stamp=str(b["t"])
            if not stamp or (last_stamp is not None and stamp<=last_stamp):raise ValueError()
            last_stamp=stamp
            c,h,l,v=(number(b.get(k)) for k in ("c","h","l","v"))
            if any(x is None for x in (c,h,l,v)) or c<=0 or l<=0 or h<l or not l<=c<=h or v<0:raise ValueError()
            candles.append((c,h,l,v))
        except (KeyError,ValueError):
            return {"symbol":symbol,"action":"NO_TRADE","reason":"Invalid/unsorted candle"}
    closes=[x[0] for x in candles]
    short=sum(closes[-3:])/3
    long=sum(closes)/len(closes)
    vol_now=sum(x[3] for x in candles[-3:])/3
    vol_old=sum(x[3] for x in candles[:-3])/max(1,len(candles)-3)
    if vol_old<=0 or vol_now/vol_old<1.5:
        return {"symbol":symbol,"action":"NO_TRADE","reason":"Volume expansion unconfirmed"}
    prev_high=max(x[1] for x in candles[-4:-1])
    prev_low=min(x[2] for x in candles[-4:-1])
    last=closes[-1]
    direction="BULLISH" if last>prev_high and last>short>long else "BEARISH" if last<prev_low and last<short<long else None
    if direction is None:return {"symbol":symbol,"action":"NO_TRADE","reason":"No confirmed breakout and trend alignment"}
    return {"symbol":symbol,"action":"PAPER_CANDIDATE","direction":direction,
            "observed_at":last_stamp,"volume_expansion_proxy":round(vol_now/vol_old,3),
            "trigger_close":last,"invalidation_reference":prev_low if direction=="BULLISH" else prev_high,
            "method":"confirmed breakout, moving-average slope and volume proxy",
            "execution":"NONE","quote_verified":False,
            "reason":"Research/paper candidate only; requires fresh tradable bid/ask, spread, session, budget and risk controls before execution"}
