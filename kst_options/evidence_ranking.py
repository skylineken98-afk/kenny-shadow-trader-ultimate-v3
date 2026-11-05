"""Measured option activity and sector-relative-strength research ranking.

Never substitute a last-trade size, quote size, or scanner score for daily
contract volume. Daily volume and open interest may be unavailable, delayed,
or sampled. No institutional order-flow or profit-probability claims.
"""
from datetime import datetime, timezone
from math import isfinite

SECTORS = {
    "AAPL":"XLK","MSFT":"XLK","NVDA":"XLK","AMD":"XLK","AVGO":"XLK",
    "GOOGL":"XLC","META":"XLC","AMZN":"XLY","TSLA":"XLY",
    "JPM":"XLF","BAC":"XLF","SOFI":"XLF","HOOD":"XLF","COIN":"XLF",
    "XOM":"XLE","CVX":"XLE","LLY":"XLV","PFE":"XLV",
    "WMT":"XLP","COST":"XLP","CAT":"XLI","BA":"XLI",
    "RIVN":"XLY","DIA":"SPY","IWM":"SPY","QQQ":"SPY",
    "XLK":"SPY","XLF":"SPY","XLE":"SPY","XLV":"SPY",
    "XLI":"SPY","GLD":"SPY","SLV":"SPY","TLT":"SPY","SPY":"SPY"
}

def number(value):
    try:
        n=float(value)
        return n if isfinite(n) else None
    except (TypeError, ValueError, OverflowError):
        return None

def nonnegative_int(value):
    n=number(value)
    if n is None or n<0 or int(n)!=n:return None
    return int(n)

def positive_ratio(num,den):
    return round(num/den,3) if num is not None and den is not None and den>0 else None

def activity(contract_volume=None, open_interest=None, historical_volume=None,
             as_of=None, oi_date=None, source=""):
    """All metrics remain unknown without independently supplied values.

    historical_volume is a list of previous daily contract bars, not today's
    cumulative volume. Three prior observations required for baseline.
    """
    volume=nonnegative_int(contract_volume)
    oi=nonnegative_int(open_interest)
    baseline=None
    if isinstance(historical_volume,list):
        prior=[nonnegative_int(v) for v in historical_volume]
        prior=[v for v in prior if v is not None]
        if len(prior)>=3:baseline=sum(prior[-5:])/len(prior[-5:])
    ratio=positive_ratio(volume,baseline)
    vol_oi=positive_ratio(volume,oi)
    unusual = None if ratio is None else ratio>=2
    return {"contract_volume":volume,"open_interest":oi,"volume_oi_ratio":vol_oi,
            "historical_avg_daily_volume":round(baseline,2) if baseline is not None else None,
            "relative_contract_volume":ratio,"unusual_volume_proxy":unusual,
            "volume_as_of":as_of,"open_interest_date":oi_date,"source":source,
            "is_institutional_flow":False}

def relative_strength(underlying, sector, underlying_prior, underlying_now,
                      sector_prior, sector_now, as_of=None):
    u0,u1,s0,s1=(number(v) for v in
                 (underlying_prior,underlying_now,sector_prior,sector_now))
    if None in (u0,u1,s0,s1) or min(u0,u1,s0,s1)<=0:return None
    return {"sector_etf":sector,
            "underlying_5d_return_pct":round((u1/u0-1)*100,3),
            "sector_5d_return_pct":round((s1/s0-1)*100,3),
            "relative_strength_pct_points":round(((u1/u0)-(s1/s0))*100,3),
            "as_of":as_of,
            "note":"Prior completed daily closes, not live capital flows."}

def rank_with_evidence(candidate, activity_data=None, sector_data=None):
    """Bounded, transparent score; absent evidence never masquerades as zero flow."""
    base=number(candidate.get("score"))
    if base is None or not 0<=base<=100:raise ValueError("Bad base score")
    a=activity_data or {}
    rs=sector_data or {}
    vol=nonnegative_int(a.get("contract_volume"))
    oi=nonnegative_int(a.get("open_interest"))
    rv=number(a.get("relative_contract_volume"))
    vr=number(a.get("volume_oi_ratio"))
    rel=number(rs.get("relative_strength_pct_points"))
    score=0.70*base
    checks=0
    # Each absent metric receives the *structural baseline* rather than an
    # artificial zero or perfect score. Verified observations adjust ranking.
    def contribution(weight, value):
        return weight*(base/100 if value is None else min(1,max(0,value)))
    if vol is not None:checks+=1
    score+=contribution(7,None if vol is None else vol/500)
    if oi is not None:checks+=1
    score+=contribution(7,None if oi is None else oi/1000)
    if rv is not None and rv>=0:checks+=1
    score+=contribution(8,None if rv is None or rv<0 else rv/2)
    if vr is not None and vr>=0:checks+=1
    score+=contribution(3,None if vr is None or vr<0 else vr)
    if rel is not None:checks+=1
    side=1 if candidate.get("option_type")=="CALL" else -1
    score+=contribution(5,None if rel is None else max(0,side*rel)/3)
    final=max(0,min(100,score))
    output=dict(candidate)
    risk=dict(output.get("risk_snapshot") or {})
    risk["ranking_evidence"]={
        "base_structural_score":round(base,3),
        "measured_evidence_items":checks,
        "expected_evidence_items":5,
        "activity":a,
        "sector_relative_strength":rs,
        "score_method":"70% base + 30% volume/OI/unusual-volume/sector evidence (missing metrics carry base-neutral estimate); uncalibrated heuristic",
        "score_is_probability":False}
    output["risk_snapshot"]=risk
    output["score"]=round(final,3)
    return output

def sector_returns(symbols, now, history=None):
    """Compare 5-session changes using only finished daily bars; no lookahead."""
    if history is None:
        from core.market import history as history_fetch
        history=history_fetch
    from zoneinfo import ZoneInfo
    today=now.astimezone(ZoneInfo("America/New_York")).date()
    symbols=list(dict.fromkeys(symbols))
    all_syms=list(dict.fromkeys(symbols+[SECTORS.get(s,"SPY") for s in symbols]))
    closes={}
    for sym in all_syms:
        try:
            bars=history(sym,period="20d",interval="1d")
            if bars is None or bars.empty:continue
            valid=bars[[str(t.date())<str(today) for t in bars.index]]
            if len(valid)<6:continue
            last=valid.iloc[-1];prior=valid.iloc[-6]
            closes[sym]=(float(prior["Close"]),float(last["Close"]),str(valid.index[-1].date()))
        except Exception:continue
    out={}
    for sym in symbols:
        sector=SECTORS.get(sym,"SPY")
        if sym not in closes or sector not in closes:continue
        a,b,ad=closes[sym];c,d,sd=closes[sector]
        out[sym]=relative_strength(sym,sector,a,b,c,d,as_of=min(ad,sd))
    return out
