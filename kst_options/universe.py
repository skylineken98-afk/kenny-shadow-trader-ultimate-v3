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

# Index options have independent coverage. Keep SPX out of the rotating
# stock/ETF universe: an explicit empty OPTIONS_SYMBOLS must not silently
# disable or impersonate index monitoring.
PRIORITY_INDEX_SYMBOLS=("SPX",)

def priority_index_symbols(enabled=None):
    """Always attempt SPX once per scan when explicitly enabled.

    Index-option entitlements and the underlying cash-index feed must be
    verified separately; an attempted chain is not a validated signal.
    """
    if enabled is None: enabled=os.getenv("SPX_INDEX_SCAN_ENABLED","true")
    return list(PRIORITY_INDEX_SYMBOLS) if str(enabled).strip().lower() in ("true","1","yes") else []

def scan_symbols(rotating, priority=None):
    """Include priority indexes exactly once, regardless of rotation/config."""
    if priority is None: priority=priority_index_symbols()
    return list(dict.fromkeys([*priority,*rotating]))

def universe(raw=None):
    """Honor explicit deployment configuration; cap cost and skip bad symbols."""
    if raw is None:raw=os.getenv("OPTIONS_SYMBOLS")
    if not raw or not raw.strip(): return list(DEFAULT_SYMBOLS)
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

def rotating_batch(symbols, now, batch_size=12, cadence_seconds=300):
    """Round-robin sampling across scan cycles to bound provider requests.

    Does not assert that every symbol is scanned on every cycle; an interrupted
    scanner may leave gaps. Logs should expose active batch coverage.
    """
    symbols=list(dict.fromkeys(symbols))
    if not symbols:return []
    n=min(len(symbols),max(1,int(batch_size)))
    cadence=max(300,int(cadence_seconds))
    slot=int(now.timestamp())//cadence
    offset=(slot*n)%len(symbols)
    return (symbols[offset:]+symbols[:offset])[:n]

def enrichment_shortlist(candidates, budgets=(30,50,100,200,500,1000,3000),
                         limit=36):
    """Cover contracts likely to be published across categories and budgets.

    Bounded discovery: never make a separate OI HTTP call for every contract in
    an option chain. The returned set is NOT a complete market sample.
    """
    rows=[c for c in candidates if c.get("quality_label")=="QUALIFIED"]
    seen=set();out=[]
    # Large, small, then intermediate budgets; include all expiry categories.
    order=[3000]+[b for b in budgets if b!=3000]
    for budget in order:
        for cat in ("0DTE","Swings","LEAPS"):
            eligible=(c for c in rows if c.get("category")==cat
                      and (c.get("entry_ask") or 0)>0
                      and c["entry_ask"]*100<=budget)
            for c in diverse_choices(eligible,3):
                key=c.get("contract")
                if not key or key in seen:continue
                seen.add(key);out.append(c)
                if len(out)>=limit:return out
    return out
