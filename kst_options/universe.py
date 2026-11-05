"""Bounded, sector-diverse option-chain research universe.

Not a claim of exhaustive market coverage. Broker/data entitlements and
scan duration determine actual eligible universe.
"""
import os
import re

# Multiple sectors and ETFs, rather than defaulting to SPY/QQQ/IWM only.
DEFAULT_SYMBOLS=(
    "SPY","QQQ","IWM","DIA",
    "AAPL","MSFT","NVDA","AMD","AVGO","GOOGL","META","AMZN",
    "JPM","BAC","XLF","XOM","CVX","XLE",
    "LLY","PFE","XLV","WMT","COST",
    "CAT","BA","XLI","GLD","SLV","TLT",
    "TSLA","COIN","SOFI","HOOD","RIVN"
)
MAX_SYMBOLS=60

def universe(raw=None):
    """Honor explicit deployment configuration; cap cost and skip bad symbols."""
    if raw is None:raw=os.getenv("OPTIONS_SYMBOLS")
    if raw is None: return list(DEFAULT_SYMBOLS)
    chosen=[]
    for item in raw.split(","):
        symbol=item.strip().upper()
        if not re.fullmatch(r"[A-Z]{1,6}",symbol) or symbol in chosen:continue
        chosen.append(symbol)
        if len(chosen)>=MAX_SYMBOLS:break
    return chosen

def diverse_choices(candidates,limit=3):
    """Take the strongest candidate from each underlying first.

    Never add a weak/unqualified idea just to fill a slot. Structural ranking
    is not a win rate; actual option volume/open interest require a feed.
    """
    if limit<=0:return []
    ranked=sorted(candidates,key=lambda c:(
        c.get("quality_label")!="QUALIFIED",
        not str(c.get("context_label") or "").endswith("_SETUP_ALIGNED"),
        -float(c.get("score") or 0),c.get("contract") or ""))
    out=[];underlyings=set();contracts=set()
    for c in ranked:
        symbol=c.get("underlying")
        if not symbol or symbol in underlyings or c.get("contract") in contracts:continue
        out.append(c);underlyings.add(symbol);contracts.add(c["contract"])
        if len(out)>=limit:return out
    for c in ranked:
        if c.get("contract") in contracts:continue
        out.append(c);contracts.add(c["contract"])
        if len(out)>=limit:break
    return out
