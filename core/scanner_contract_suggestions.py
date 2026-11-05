"""Match the latest directional scanner signals to priced option research.

Read-only recommendations; no quote is presented as executable.
"""
from datetime import datetime, timezone
import math

def _stamp(value):
    if not value:return None
    try:
        dt=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (ValueError, TypeError, OverflowError):return None

def _float(value):
    try:
        v=float(value)
        return v if math.isfinite(v) else None
    except (ValueError, TypeError, OverflowError):return None

def match_signal_contracts(signals, contracts, now=None, max_cost=500, max_quote_age_minutes=15, max_signal_age_minutes=90):
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:raise ValueError("UTC-aware now required")
    latest={}
    for s in sorted(signals,key=lambda x:str(x.get("created_at") or ""),reverse=True):
        symbol=s.get("symbol")
        if not symbol or symbol in latest:continue
        latest[symbol]=s
    rows=[]
    for sym, signal in latest.items():
        side=signal.get("side")
        stamp=_stamp(signal.get("created_at"))
        age=(now-stamp).total_seconds()/60 if stamp else None
        eligible_signal=signal.get("status")=="SETUP" and side in ("BULLISH","BEARISH") and age is not None and 0<=age<=max_signal_age_minutes
        matches=[]
        if eligible_signal:
            for c in contracts:
                if c.get("underlying")!=sym or c.get("quality_label")!="QUALIFIED":continue
                if c.get("option_type")!=("CALL" if side=="BULLISH" else "PUT"):continue
                if c.get("state") not in ("OPEN",None):continue
                quote=_stamp(c.get("quote_at"))
                quote_age=(now-quote).total_seconds()/60 if quote else None
                ask=_float(c.get("entry_ask"));bid=_float(c.get("entry_bid"))
                if quote_age is None or not 0<=quote_age<=max_quote_age_minutes:continue
                if ask is None or bid is None or bid<0 or ask<=0 or bid>ask:continue
                # Standard US equity ETF options have 100 shares per contract.
                cost=round(ask*100,2)
                if cost>max_cost:continue
                context=c.get("context_label")
                if context not in (side+"_SETUP_ALIGNED",):continue
                score=_float(c.get("score"))
                if score is None:continue
                spread=(ask-bid)/((ask+bid)/2) if ask+bid else 1
                matches.append((score,-spread,c.get("quote_at") or "",c,cost))
        matches.sort(reverse=True,key=lambda x:(x[0],x[1],x[2]))
        best=matches[0] if matches else None
        reason=("Latest signal not a fresh confirmed setup" if not eligible_signal else
                "No direction-aligned qualified contract <= $500 with a recent quote")
        rows.append({"symbol":sym,"side":side,"status":signal.get("status"),
                     "signal_at":signal.get("created_at"),"signal_age_minutes":round(age,1) if age is not None else None,
                     "entry":signal.get("entry"),"stop":signal.get("stop"),"target":signal.get("target"),
                     "suggestion":best[3] if best else None,
                     "premium_cost":best[4] if best else None,
                     "reason":None if best else reason})
    return rows
