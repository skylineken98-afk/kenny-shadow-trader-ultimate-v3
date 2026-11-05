"""Read-only cross-sector market pulse from genuine stock/ETF snapshot data.

Ranks *observed* price movers, not future winners or verified institutional flows.
Every report explicitly describes scan coverage and data quality.
"""
import os
from datetime import datetime, timezone
from math import isfinite
from .engine import stamp, parse

SECTOR_ETFS=("XLK","XLF","XLE","XLV","XLY","XLP","XLI","XLB","XLU","XLRE","XLC")
DEFAULT_WATCH=("SPY","QQQ","IWM","AAPL","MSFT","NVDA","AMD","AVGO",
               "META","GOOGL","AMZN","TSLA","JPM","BAC","XOM","CVX",
               "LLY","PFE","WMT","COST","CAT","BA","COIN","HOOD","SOFI")
def safe_number(value):
    try:
        value=float(value)
        return value if isfinite(value) else None
    except (TypeError,ValueError,OverflowError):
        return None

def tracked_symbols(extra=None):
    raw=os.getenv("MARKET_PULSE_SYMBOLS","") if extra is None else extra
    supplied=[s.strip().upper() for s in str(raw).split(",")]
    import re
    supplied=[s for s in supplied if re.fullmatch(r"[A-Z]{1,5}",s)]
    return list(dict.fromkeys((*SECTOR_ETFS,*DEFAULT_WATCH,*supplied)))[:100]

def classify_snapshots(snapshots,now, symbols=None):
    """Rank actual session changes; do not compare partial volume with full-day volume as RVOL."""
    if not isinstance(snapshots,dict):snapshots={}
    symbols=list(symbols or tracked_symbols())
    rows=[]
    for symbol in symbols:
        item=snapshots.get(symbol) or {}
        day=item.get("dailyBar") or {}
        prev=item.get("prevDailyBar") or {}
        latest=item.get("latestTrade") or {}
        old=safe_number(prev.get("c"))
        price=safe_number(latest.get("p"))
        if price is None:price=safe_number(day.get("c"))
        if old is None or old<=0 or price is None or price<=0:continue
        t=latest.get("t") or day.get("t")
        try:
            observed=parse(t)
            if observed.tzinfo is None or not 0<=(now-observed).total_seconds()<=900:continue
        except (ValueError,TypeError):continue
        volume=safe_number(day.get("v"))
        previous_volume=safe_number(prev.get("v"))
        change=round(100*(price/old-1),3)
        rows.append({"symbol":symbol,"change_pct":change,"last_price":price,
                     "previous_close":old,"day_volume":int(volume) if volume is not None and volume>=0 else None,
                     "previous_full_day_volume":int(previous_volume) if previous_volume is not None and previous_volume>=0 else None,
                     "as_of":stamp(observed),
                     "volume_note":"Session-to-date volume vs previous FULL session: not time-adjusted RVOL and not fund flow."})
    rank=lambda x:(-abs(x["change_pct"]),x["symbol"])
    bulls=sorted((r for r in rows if r["change_pct"]>0),key=lambda r:(-r["change_pct"],r["symbol"]))[:10]
    bears=sorted((r for r in rows if r["change_pct"]<0),key=lambda r:(r["change_pct"],r["symbol"]))[:10]
    sectors=sorted((r for r in rows if r["symbol"] in SECTOR_ETFS),key=lambda r:(-r["change_pct"],r["symbol"]))
    by_symbol={r["symbol"]:r for r in rows}
    sp=by_symbol.get("SPY")
    for item in sectors:
        item["vs_spy_percentage_points"]=round(item["change_pct"]-sp["change_pct"],3) if sp else None
    return {"as_of":stamp(now),"coverage":{"requested":len(symbols),"valid":len(rows),"universe":"configured limited watchlist; not the entire market"},
            "biggest_bulls":bulls,"biggest_bears":bears,
            "sector_leaders":sectors[:5],"sector_laggards":list(reversed(sectors[-5:])),
            "largest_absolute_moves":sorted(rows,key=rank)[:10],
            "market_drivers":{"status":"UNVERIFIED","note":"Prices and sector relative strength identify where activity occurred, not WHY. News catalysts require independent verification; do not label volume as capital inflows."},
            "future_move_prediction":None,"institutional_net_flows":None,
            "source":"Alpaca stock/ETF snapshots; permitted feed and timestamp availability vary"}

def refresh(store,now,http=None):
    import requests
    fetch=http or requests.get
    feed=os.getenv("STOCK_FEED","iex").strip() or "iex"
    if feed not in ("iex","sip"):raise ValueError("STOCK_FEED must be iex or sip")
    symbols=tracked_symbols()
    response=fetch("https://data.alpaca.markets/v2/stocks/snapshots",
        params={"symbols":",".join(symbols),"feed":feed},
        headers={"APCA-API-KEY-ID":os.environ["ALPACA_API_KEY"].strip(),
                 "APCA-API-SECRET-KEY":os.environ["ALPACA_API_SECRET"].strip()},timeout=25)
    if not response.ok:raise RuntimeError("Market pulse stock/ETF feed unavailable")
    payload=classify_snapshots(response.json(),now,symbols)
    if not payload["coverage"]["valid"]:raise RuntimeError("Market pulse has no recent verified snapshots")
    payload["feed"]=feed
    store.call("POST","kst_market_pulse",
        data={"id":"latest","observed_at":stamp(now),"payload":payload},
        prefer="resolution=merge-duplicates,return=minimal")
    return payload
